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
    saldo = models.DecimalField(max_digits=15, decimal_places=2, default=0.00) 

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
# --- 3. MODELO TRANSACCION (Lógica de Actualización de Saldo Añadida) ---
# ========================================================

class Transaccion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    cuenta = models.ForeignKey(Cuenta, on_delete=models.CASCADE) 
    monto = models.DecimalField(max_digits=15, decimal_places=2)
    tipo = models.CharField(max_length=7, choices=TIPO_INGRESO_EGRESO) 
    
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True) 
    
    fecha = models.DateField()
    descripcion = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    # 🌟 REFINAMIENTO AÑADIDO para robustez y filtrado 🌟
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
    # 💡 LÓGICA CRÍTICA DE MANTENIMIENTO DE SALDO (Save) 💡
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_monto = Decimal('0.00')
        old_cuenta = None

        if not is_new:
            try:
                # Obtener el estado anterior de la transacción de la base de datos
                old_transaccion = Transaccion.objects.get(pk=self.pk)
                old_monto = old_transaccion.monto
                old_cuenta = old_transaccion.cuenta
            except Transaccion.DoesNotExist:
                pass 

        # 1. Llamar al save original para guardar la nueva transacción/modificación
        super().save(*args, **kwargs)

        # 2. Lógica de ajuste de saldos
        
        # Si la cuenta cambió (edición de cuenta):
        if old_cuenta and old_cuenta != self.cuenta:
            # Revertir el monto anterior en la cuenta antigua
            old_cuenta.saldo -= old_monto
            old_cuenta.save()
        
        # Si la cuenta no cambió O si es una nueva transacción O si la cuenta cambió:
        # Se revierte el monto antiguo del saldo (o 0 si es nueva)
        self.cuenta.saldo -= old_monto 
        
        # Se aplica el nuevo monto al saldo
        self.cuenta.saldo += self.monto
        
        # Guardar la cuenta (esto cubre los casos de nueva, edición de monto, y edición de cuenta)
        self.cuenta.save()

    # ❌ ELIMINACIÓN DEL MÉTODO delete() ❌
    # La lógica de ajuste de saldo para la eliminación se maneja ahora
    # EXCLUSIVAMENTE en la vista `eliminar_transaccion` para evitar la doble reversión.


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
        validators=[MinValueValidator(0.01)],
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

