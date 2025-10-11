from django.db import models
from django.contrib.auth.models import User

# --- CHOICES ---
TIPOS_CUENTA = [
    ('AHORROS', 'Ahorros'),
    ('CHEQUES', 'Cheques/Corriente'),
    ('INVERSION', 'Inversión'),
    ('TARJETA', 'Tarjeta de Crédito'),
    ('EFECTIVO', 'Efectivo'),
]

TIPOS_TRANSACCION = [
    ('INGRESO', 'Ingreso'),
    ('GASTO', 'Gasto'),
]

# --- 1. MODELO CUENTA ---
class Cuenta(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=TIPOS_CUENTA)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    class Meta:
        # Asegura que cada usuario tenga nombres de cuenta únicos
        unique_together = ('usuario', 'nombre')
        verbose_name_plural = "Cuentas"

    def __str__(self):
        return f"{self.nombre} ({self.usuario.username})"

# --- 2. MODELO CATEGORIA (CORREGIDO) ---
class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categorias')
    
    class Meta:
        # Asegura que cada usuario tenga nombres de categoría únicos
        unique_together = ('usuario', 'nombre') 
        verbose_name_plural = "Categorías"

    def __str__(self):
        return self.nombre

# --- 3. MODELO TRANSACCION ---
class Transaccion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    cuenta = models.ForeignKey(Cuenta, on_delete=models.CASCADE)
    monto = models.DecimalField(max_digits=15, decimal_places=2)
    # Usa el TIPOS_TRANSACCION definido arriba
    tipo = models.CharField(max_length=7, choices=TIPOS_TRANSACCION) 
    
    # Clave foránea al modelo Categoria
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True) 
    
    fecha = models.DateField()
    descripcion = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Transacciones"
        ordering = ['-fecha', '-fecha_creacion']

    def __str__(self):
        return f"{self.tipo} de {self.monto} en {self.cuenta.nombre}"

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone # Necesario para el campo de fecha

User = get_user_model() # Asumiendo que usas el modelo de usuario por defecto

# ... (Definiciones de los modelos Cuenta, Categoria, Transaccion) ...

# 🚨 NUEVO MODELO NECESARIO 🚨
class TransaccionRecurrente(models.Model):
    # La transacción recurrente necesita los mismos campos que la Transacción normal
    cuenta = models.ForeignKey('Cuenta', on_delete=models.CASCADE)
    categoria = models.ForeignKey('Categoria', on_delete=models.SET_NULL, null=True, blank=True)
    
    TIPO_CHOICES = [
        ('INGRESO', 'Ingreso'),
        ('GASTO', 'Gasto'),
    ]
    tipo = models.CharField(max_length=7, choices=TIPO_CHOICES)
    
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion = models.CharField(max_length=255)
    
    # Campos CRÍTICOS para la recurrencia
    FRECUENCIA_CHOICES = [
        ('DIARIA', 'Diaria'),
        ('SEMANAL', 'Semanal'),
        ('MENSUAL', 'Mensual'),
        ('ANUAL', 'Anual'),
    ]
    frecuencia = models.CharField(max_length=10, choices=FRECUENCIA_CHOICES)
    
    proximo_pago = models.DateField(default=timezone.localdate) # La fecha que el comando revisará
    
    esta_activa = models.BooleanField(default=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recurrente: {self.descripcion} - {self.frecuencia}"
        
    # Método esencial para que tu comando funcione correctamente
    def calcular_siguiente_fecha(self):
        # NOTA: Debes implementar la lógica real de cálculo de fecha aquí
        # Por ahora, solo devolverá una fecha futura simple
        from datetime import timedelta
        if self.frecuencia == 'MENSUAL':
            return self.proximo_pago + timedelta(days=30)
        else:
            return self.proximo_pago + timedelta(days=7) # Ejemplo

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator 

User = get_user_model() 

# ... (Tus modelos existentes: Cuenta, Categoria, Transaccion, TransaccionRecurrente) ...

class Presupuesto(models.Model):
    """Define el límite de gasto para una categoría en un periodo específico."""
    
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # El presupuesto siempre está vinculado a una categoría de gasto
    categoria = models.ForeignKey('Categoria', on_delete=models.CASCADE)
    
    # El monto límite debe ser positivo
    monto_limite = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)], # Asegura que el límite sea mayor a cero
        help_text="Monto máximo que deseas gastar en esta categoría."
    )
    
    # Periodicidad: Usaremos el mes y año para definir el periodo
    mes = models.PositiveSmallIntegerField() # 1 para Enero, 12 para Diciembre
    anio = models.PositiveSmallIntegerField()
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Esto asegura que un usuario solo pueda tener UN presupuesto por categoría por mes/año
        unique_together = ('usuario', 'categoria', 'mes', 'anio')
        verbose_name = "Presupuesto Mensual"
        verbose_name_plural = "Presupuestos Mensuales"
        
    def __str__(self):
        return f"Presupuesto {self.categoria.nombre} ({self.mes}/{self.anio}) - ${self.monto_limite}"



from django import forms
from .models import Cuenta, Transaccion, Presupuesto, Categoria
from django.utils import timezone # Para obtener la fecha actual por defecto

# --- Formulario de Presupuestos ---
class PresupuestoForm(forms.ModelForm):
    # El usuario no debe seleccionar su propio ID, se asigna en la vista.
    # El mes y el año se inicializan al mes actual.
    
    class Meta:
        model = Presupuesto
        fields = ['categoria', 'monto_limite', 'mes', 'anio']
        widgets = {
            # Establecer los valores por defecto al mes y año actual
            'mes': forms.Select(attrs={'class': 'form-control'}, 
                                choices=[(i, str(i)) for i in range(1, 13)]),
            'anio': forms.NumberInput(attrs={'class': 'form-control', 
                                              'min': timezone.localdate().year,
                                              'max': timezone.localdate().year + 5}),
            'monto_limite': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
        }

    # CRÍTICO: Sobreescribir el __init__ para filtrar categorías por usuario
    def __init__(self, *args, **kwargs):
        # El pop() es para obtener el usuario antes de inicializar el form
        self.request = kwargs.pop('request', None) 
        super().__init__(*args, **kwargs)
        
        if self.request and self.request.user.is_authenticated:
            # Filtra las categorías disponibles solo a las del usuario actual
            self.fields['categoria'].queryset = Categoria.objects.filter(
                usuario=self.request.user
            ).order_by('nombre')

