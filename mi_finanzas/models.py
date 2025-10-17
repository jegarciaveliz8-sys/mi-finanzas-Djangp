from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator 
from django.utils import timezone
from datetime import timedelta 
from decimal import Decimal 
# IMPORTACIÓN CRÍTICA: Se necesita F para operaciones atómicas
from django.db.models import F 

User = get_user_model() 

# ========================================================
# --- CHOICES (sin cambios) ---
# ========================================================

TIPOS_CUENTA = [
    ('AHORROS', 'Ahorros'),
    ('CHEQUES', 'Cheques/Corriente'),
    ('INVERSION', 'Inversión'),
    ('TARJETA', 'Tarjeta de Crédito'),
    ('EFECTIVO', 'Efectivo'),
    ('PRESTAMO', 'Préstamo Personal/Deuda'), 
    ('HIPOTECA', 'Hipoteca'), 
    ('AUTO', 'Préstamo de Auto'), 
    ('RETIRO', 'Cuenta de Retiro/Pensión'), 
    ('CRYPTO', 'Criptomonedas'),
    ('CDT', 'Certificado de Depósito (CDT)'), 
    ('WALLET', 'Billetera Digital/PayPal'), 
    ('METAS', 'Ahorro para Metas Específicas'), 
    ('ACTIVO_FIJO', 'Activo Fijo (Valor Neto)'), 
    ('COBRO', 'Cuentas por Cobrar'), 
]

TIPO_INGRESO_EGRESO = [
    ('INGRESO', 'Ingreso'),
    ('EGRESO', 'Egreso'),
]

FRECUENCIA_CHOICES = [
    ('DIARIA', 'Diaria'),
    ('SEMANAL', 'Semanal'),
    ('MENSUAL', 'Mensual'),
    ('ANUAL', 'Anual'),
]

# ========================================================
# --- 1. MODELO CUENTA (sin cambios) ---
# ========================================================

class Cuenta(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=15, choices=TIPOS_CUENTA) 
    saldo = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00')) 

    class Meta:
        unique_together = ('usuario', 'nombre')
        verbose_name_plural = "Cuentas"

    def __str__(self):
        return f"{self.nombre} ({self.usuario.username})"

# ========================================================
# --- 2. MODELO CATEGORIA (sin cambios) ---
# ========================================================

class Categoria(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categorias')
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(
        max_length=7, 
        choices=TIPO_INGRESO_EGRESO, 
        default='EGRESO'
    )
    
    class Meta:
        unique_together = ('usuario', 'nombre', 'tipo') 
        verbose_name_plural = "Categorías"

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.nombre}"

# ========================================================
# --- 3. MODELO TRANSACCION (Lógica Crítica Corregida) ---
# ========================================================

class Transaccion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    cuenta = models.ForeignKey(Cuenta, on_delete=models.CASCADE) 
    # Monto se almacena como POSITIVO (valor absoluto).
    monto = models.DecimalField(max_digits=15, decimal_places=2) 
    tipo = models.CharField(max_length=7, choices=TIPO_INGRESO_EGRESO) 
    
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True) 
    
    fecha = models.DateField()
    descripcion = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    es_transferencia = models.BooleanField(default=False) 
    
    transaccion_relacionada = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='par_transferencia'
    )
    
    class Meta:
        verbose_name_plural = "Transacciones"
        ordering = ['-fecha', '-fecha_creacion']

    def __str__(self):
        return f"{self.tipo} de {self.monto} en {self.cuenta.nombre}"

    # ------------------------------------------------------------------
    # LÓGICA AUXILIAR
    # ------------------------------------------------------------------

    def _get_signed_monto(self, monto: Decimal, tipo: str) -> Decimal:
        """Devuelve el monto con el signo correcto: positivo para INGRESO, negativo para EGRESO."""
        if tipo == 'EGRESO':
            return -monto
        return monto
    
    # ------------------------------------------------------------------
    # LÓGICA CRÍTICA DE MANTENIMIENTO DE SALDO (Save) - ✅ CORREGIDO con F()
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # 1. Reversión (Solo si es Edición)
        if not is_new:
            try:
                # Obtener la transacción y cuenta ANTERIORES
                old_transaccion = Transaccion.objects.get(pk=self.pk)
                old_cuenta = old_transaccion.cuenta
                
                # Calcular el monto anterior con signo
                old_signed_monto = self._get_signed_monto(old_transaccion.monto, old_transaccion.tipo)
                
                # Revertir el impacto de la transacción antigua:
                # Se suma el inverso (un egreso negativo se revierte sumando un valor positivo).
                
                # a. Si la cuenta fue cambiada: Revertir de la cuenta ANTERIOR
                if old_cuenta != self.cuenta:
                    Cuenta.objects.filter(pk=old_cuenta.pk).update(
                        saldo=F('saldo') - old_signed_monto # Revertir el saldo antiguo
                    )
                    
                # b. Revertir de la cuenta ACTUAL (aplica si la cuenta no fue cambiada o para el punto a)
                # OJO: La reversión debe hacerse SIEMPRE sobre la cuenta antes de aplicar el nuevo monto.
                # Si la cuenta no fue cambiada, F('saldo') - old_signed_monto ya contiene el monto revertido.
                # Simplificamos: revertimos de la cuenta actual para evitar doble reversión si la cuenta no cambió.
                if old_cuenta == self.cuenta:
                    Cuenta.objects.filter(pk=self.cuenta.pk).update(
                        saldo=F('saldo') - old_signed_monto # Revertir en la misma cuenta
                    )

            except Transaccion.DoesNotExist:
                # Si no existe, no hay nada que revertir (esto no debería pasar en una edición)
                pass 

        # 2. Llamar al save original
        super().save(*args, **kwargs)

        # 3. Aplicación del Nuevo Saldo
        
        # Calcular el nuevo monto con signo
        current_signed_monto = self._get_signed_monto(self.monto, self.tipo)
        
        # Aplicar el nuevo monto a la cuenta actual:
        # F('saldo') + current_signed_monto (suma si es INGRESO, resta si es EGRESO)
        Cuenta.objects.filter(pk=self.cuenta.pk).update(
            saldo=F('saldo') + current_signed_monto
        )
        # Nota: Los tests requerirán self.cuenta.refresh_from_db() para ver el nuevo saldo.

    # ------------------------------------------------------------------
    # LÓGICA CRÍTICA DE MANTENIMIENTO DE SALDO (Delete) - ✅ IMPLEMENTADO con F()
    # ------------------------------------------------------------------
    
    def delete(self, *args, **kwargs):
        # El delete debe REVERTIR el impacto del saldo antes de eliminar la transacción.
        
        # Calcular el monto de la transacción a eliminar con su signo
        signed_monto = self._get_signed_monto(self.monto, self.tipo)
        
        # Revertir el impacto de la transacción en la cuenta
        # Sumar el inverso del monto firmado: si era un EGRESO (-100), sumamos 100.
        # Si era un INGRESO (100), restamos 100.
        Cuenta.objects.filter(pk=self.cuenta.pk).update(
            saldo=F('saldo') - signed_monto 
        )
        
        # Llamar al delete original
        super().delete(*args, **kwargs)


# ========================================================
# --- 4. MODELO TRANSACCION RECURRENTE (sin cambios) ---
# ========================================================

class TransaccionRecurrente(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE) 
    cuenta = models.ForeignKey(Cuenta, on_delete=models.CASCADE)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    
    tipo = models.CharField(max_length=7, choices=TIPO_INGRESO_EGRESO)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion = models.CharField(max_length=255)
    
    frecuencia = models.CharField(max_length=10, choices=FRECUENCIA_CHOICES)
    proximo_pago = models.DateField(default=timezone.localdate) 
    esta_activa = models.BooleanField(default=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recurrente: {self.descripcion} - {self.frecuencia}"
        
    def calcular_siguiente_fecha(self):
        if self.frecuencia == 'MENSUAL':
            return self.proximo_pago + timedelta(days=30) 
        elif self.frecuencia == 'SEMANAL':
            return self.proximo_pago + timedelta(days=7)
        else:
            return self.proximo_pago + timedelta(days=1)

# ========================================================
# --- 5. MODELO PRESUPUESTO (sin cambios) ---
# ========================================================

class Presupuesto(models.Model):
    """Define el límite de gasto para una categoría en un periodo específico."""
    
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE) 
    
    monto_limite = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Monto máximo que deseas gastar en esta categoría."
    )
    
    mes = models.PositiveSmallIntegerField() 
    anio = models.PositiveSmallIntegerField()
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'categoria', 'mes', 'anio')
        verbose_name = "Presupuesto Mensual"
        verbose_name_plural = "Presupuestos Mensuales"
        
    def __str__(self):
        return f"Presupuesto {self.categoria.nombre} ({self.mes}/{self.anio}) - ${self.monto_limite}"

