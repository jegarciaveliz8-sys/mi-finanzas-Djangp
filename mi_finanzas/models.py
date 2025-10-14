from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator 
from django.utils import timezone
from datetime import timedelta # Necesario para TransaccionRecurrente

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
]

# Usado para Transacción, Categoría y TransacciónRecurrente
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
    tipo = models.CharField(max_length=10, choices=TIPOS_CUENTA)
    # 🔑 CORRECCIÓN: Usando 'saldo' en lugar de 'balance' para consistencia con vistas
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
    
    # 🔑 CORRECCIÓN CRÍTICA: CAMPO 'TIPO' AÑADIDO (Requerido por CategoriaForm)
    tipo = models.CharField(
        max_length=7, 
        choices=TIPO_INGRESO_EGRESO, 
        default='EGRESO'
    )
    
    class Meta:
        # Añadido 'tipo' para permitir que el usuario tenga 'Viajes-Ingreso' y 'Viajes-Egreso'
        unique_together = ('usuario', 'nombre', 'tipo') 
        verbose_name_plural = "Categorías"

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.nombre}"

# ========================================================
# --- 3. MODELO TRANSACCION ---
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
    
    class Meta:
        verbose_name_plural = "Transacciones"
        ordering = ['-fecha', '-fecha_creacion']

    def __str__(self):
        return f"{self.tipo} de {self.monto} en {self.cuenta.nombre}"

# ========================================================
# --- 4. MODELO TRANSACCION RECURRENTE ---
# ========================================================

class TransaccionRecurrente(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE) # 🔑 Añadido
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
        
    # Método esencial para que tu comando cron funcione
    def calcular_siguiente_fecha(self):
        # Implementación simple, usarías dateutil.relativedelta para precisión
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
    # Solo puedes presupuestar categorías de egreso/gasto, por eso se vincula a Categoria
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

