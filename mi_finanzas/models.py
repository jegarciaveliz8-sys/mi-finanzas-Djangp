from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator 
from django.utils import timezone
from datetime import timedelta 
from decimal import Decimal 

User = get_user_model() 

# ========================================================
# --- CHOICES ---
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
# --- 1. MODELO CUENTA ---
# ========================================================

class Cuenta(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=15, choices=TIPOS_CUENTA) 
    # El campo de saldo es 'saldo', NO 'balance'.
    saldo = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00')) 

    class Meta:
        unique_together = ('usuario', 'nombre')
        verbose_name_plural = "Cuentas"

    def __str__(self):
        return f"{self.nombre} ({self.usuario.username})"

# ========================================================
# --- 2. MODELO CATEGORIA ---
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
# --- 3. MODELO TRANSACCION (Lógica de Actualización de Saldo) ---
# ========================================================

class Transaccion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    cuenta = models.ForeignKey(Cuenta, on_delete=models.CASCADE) 
    # NOTA: El monto DEBE guardarse como POSITIVO (valor absoluto).
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
    # NUEVA LÓGICA DE NEGOCIO: Monto con Signo
    # ------------------------------------------------------------------

    def _get_monto_ajustado(self, monto: Decimal, tipo: str) -> Decimal:
        """Devuelve el monto con el signo correcto: positivo para INGRESO, negativo para EGRESO."""
        if tipo == 'EGRESO':
            return -monto
        return monto
    
    # ------------------------------------------------------------------
    # LÓGICA CRÍTICA DE MANTENIMIENTO DE SALDO (Save) - CORREGIDA
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Montos y cuenta anteriores
        old_signed_monto = Decimal('0.00') # Monto anterior, ya con signo
        old_cuenta = None
        old_tipo = None

        if not is_new:
            try:
                # Recuperar el estado de la transacción antes de la edición
                old_transaccion = Transaccion.objects.select_related('cuenta').get(pk=self.pk)
                old_cuenta = old_transaccion.cuenta
                old_tipo = old_transaccion.tipo
                
                # Calcular el monto anterior con signo usando la nueva función auxiliar
                old_signed_monto = self._get_monto_ajustado(old_transaccion.monto, old_tipo)

            except Transaccion.DoesNotExist:
                pass 

        # 1. Llamar al save original para guardar la nueva transacción/modificación
        super().save(*args, **kwargs)

        # 2. Calcular el monto actual con signo
        # Esto asume que self.monto es un valor positivo (absoluto)
        current_signed_monto = self._get_monto_ajustado(self.monto, self.tipo)
        
        # 3. Lógica de ajuste de saldos

        # a. Si la cuenta fue cambiada (edición de cuenta):
        if old_cuenta and old_cuenta != self.cuenta:
            # Revertir el impacto del monto anterior en la cuenta antigua (suma el inverso del monto con signo)
            old_cuenta.saldo -= old_signed_monto 
            old_cuenta.save()
            
        # b. Ajustar la cuenta actual (sea nueva, editada, o cuenta cambiada):
        
        # Revertir el impacto del monto anterior (si era nueva, old_signed_monto es 0.00)
        self.cuenta.saldo -= old_signed_monto 
        
        # Aplicar el nuevo monto. Si es INGRESO suma, si es EGRESO resta.
        self.cuenta.saldo += current_signed_monto 
        
        # Guardar la cuenta 
        self.cuenta.save()

    # Se mantiene la decisión de no incluir el método delete() y manejar la reversión en la vista.


# ========================================================
# --- 4. MODELO TRANSACCION RECURRENTE ---
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
        # Implementación simple, usar dateutil.relativedelta para precisión
        if self.frecuencia == 'MENSUAL':
            # Nota: Usar timedelta(days=30) es una aproximación,
            # para mayor precisión mensual se recomienda python-dateutil.
            return self.proximo_pago + timedelta(days=30) 
        elif self.frecuencia == 'SEMANAL':
            return self.proximo_pago + timedelta(days=7)
        else:
            return self.proximo_pago + timedelta(days=1)

# ========================================================
# --- 5. MODELO PRESUPUESTO ---
# ========================================================

class Presupuesto(models.Model):
    """Define el límite de gasto para una categoría en un periodo específico."""
    
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE) 
    
    monto_limite = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))], # Uso de Decimal para MinValueValidator
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

