from django import forms
from .models import Cuenta, Transaccion, Categoria
from django.forms.widgets import TextInput, NumberInput, Select, Textarea, DateInput
# No es necesario importar 'User' si usas 'get_user_model' o asumes que ya está importado
# from django.contrib.auth.models import User 

# ----------------------------------------------------
# Formulario de Cuentas (Para el CRUD)
# ----------------------------------------------------

class CuentaForm(forms.ModelForm):
    # Usamos balance_inicial si tu modelo lo tiene, 
    # o si no, se lo renombramos a 'balance' para la entrada de datos iniciales.
    # Usaremos 'balance' aquí, pero la vista debe tratarlo como inicial.
    
    class Meta:
        model = Cuenta
        # ⚠️ CAMBIO CLAVE: Usamos 'balance' como si fuera el saldo inicial
        # (Si tu modelo tiene 'balance_inicial', úsalo en lugar de 'balance')
        fields = ['nombre', 'tipo', 'balance'] 
        widgets = {
            'nombre': TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Banco Principal'}),
            'tipo': Select(attrs={'class': 'form-select'}), # Usar form-select para mejor estilo
            'balance': NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
        }
# ... (resto del archivo TransaccionForm y LoginForm)


# ----------------------------------------------------
# Formulario de Transacciones (Para el CRUD)
# ----------------------------------------------------

class TransaccionForm(forms.ModelForm):
    
    # La fecha se representa mejor como un campo de texto con formato de calendario
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    # ESTE ES EL CONSTRUCTOR CORREGIDO QUE SOLUCIONA EL TypeError
    def __init__(self, *args, **kwargs):
        # 1. Captura y REMUEVE el argumento 'user' de kwargs
        # La vista envía: user=request.user
        # Esto previene el TypeError y obtiene el objeto usuario.
        user = kwargs.pop('user', None) 
        
        # 2. Llama al constructor de la clase base (super)
        super(TransaccionForm, self).__init__(*args, **kwargs)
        
        # 3. Usa el objeto 'user' para filtrar las opciones de las ForeignKey
        if user is not None:
            # Filtra las Cuentas: Muestra solo las cuentas del usuario
            self.fields['cuenta'].queryset = Cuenta.objects.filter(usuario=user)
            # Filtra las Categorías: Muestra solo las categorías del usuario
            self.fields['categoria'].queryset = Categoria.objects.filter(usuario=user)

            # Asegura que se aplican las clases de Bootstrap a los Select (opcional, pero limpio)
            self.fields['cuenta'].widget.attrs.update({'class': 'form-select'})
            self.fields['categoria'].widget.attrs.update({'class': 'form-select'})
            
    class Meta:
        model = Transaccion
        # Asegúrate de que 'cuenta' y 'categoria' estén aquí
        fields = ['monto', 'tipo', 'categoria', 'fecha', 'descripcion', 'cuenta']
        widgets = {
            'monto': NumberInput(attrs={'class': 'form-control'}),
            'tipo': Select(attrs={'class': 'form-control'}),
            'categoria': Select(attrs={'class': 'form-control'}), # Nota: el widget Select ya está en las importaciones
            'fecha': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'descripcion': Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'cuenta': Select(attrs={'class': 'form-control'}), # Nota: el widget Select ya está en las importaciones
        }

# ----------------------------------------------------
# Formulario de Login (Necesario para la vista user_login)
# ----------------------------------------------------

class LoginForm(forms.Form):
    # ... (El resto del código de LoginForm no se modifica)
    username = forms.CharField(
        label='Nombre de usuario',
        max_length=150,
        widget=TextInput(attrs={'class': 'form-control', 'placeholder': 'Usuario'})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'})
    )

from django import forms
from .models import Presupuesto, Categoria
from django.utils import timezone
import calendar # Necesario para obtener los nombres de los meses

# Obtener el mes y año actual
hoy = timezone.localdate()

# Definir las opciones de mes (usando nombres en español)
MESES_CHOICES = [
    (i, calendar.month_name[i]) for i in range(1, 13)
]
# Ajustar a español si es necesario, usando una lista manual:
# MESES_CHOICES = [
#     (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'), (5, 'Mayo'), (6, 'Junio'),
#     (7, 'Julio'), (8, 'Agosto'), (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
# ]

# Opciones de año (desde el actual hasta los próximos 5 años)
ANIO_CHOICES = [(y, y) for y in range(hoy.year, hoy.year + 5)]


class PresupuestoForm(forms.ModelForm):
    
    # Sobrescribir los campos Mes y Año con los Choices definidos
    mes = forms.TypedChoiceField(
        choices=MESES_CHOICES,
        coerce=int,
        initial=hoy.month, # Establece el mes actual por defecto
        label="Mes del Presupuesto"
    )

    anio = forms.TypedChoiceField(
        choices=ANIO_CHOICES,
        coerce=int,
        initial=hoy.year, # Establece el año actual por defecto
        label="Año del Presupuesto"
    )
    
    class Meta:
        model = Presupuesto
        # Incluir solo los campos que el usuario necesita llenar
        fields = ('categoria', 'monto_limite', 'mes', 'anio')
        
        widgets = {
            # Usar un campo de número con un paso para el monto
            'monto_limite': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'placeholder': 'Ej: 500.00'}),
        }
        
    def __init__(self, *args, **kwargs):
        # Aseguramos que solo se muestren categorías del usuario (si la tienes implementada)
        # Esto es avanzado, pero esencial para la seguridad.
        self.request = kwargs.pop('request', None) 
        super().__init__(*args, **kwargs)
        
        # Filtramos las categorías para que solo se vean las del usuario actual
        if self.request:
            self.fields['categoria'].queryset = Categoria.objects.filter(usuario=self.request.user)

        # Aplicar clases de estilo Bootstrap a todos los campos
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

from django import forms
from .models import Presupuesto, Categoria
# ... otras importaciones ...

class PresupuestoForm(forms.ModelForm):
    # Aquí está la corrección: añadir el constructor __init__
    def __init__(self, *args, **kwargs):
        # 1. Extrae y REMUEVE el argumento 'user' de kwargs (la clave de la solución).
        user = kwargs.pop('user', None) 
        
        # 2. Llama al constructor de la clase base (ModelForm) con los argumentos restantes.
        # Esto previene el TypeError: 'BaseModelForm.__init__() got an unexpected keyword argument 'user''
        super().__init__(*args, **kwargs)
        
        # 3. Usa el objeto 'user' para filtrar el queryset de categorías.
        if user is not None:
            # Filtra las categorías para que solo se muestren las del usuario actual
            self.fields['categoria'].queryset = Categoria.objects.filter(usuario=user)
            # Opcional: añade clases de estilo
            self.fields['categoria'].widget.attrs.update({'class': 'form-select'})

    class Meta:
        model = Presupuesto
        fields = ['categoria', 'monto_limite']
        # ... otros detalles Meta ...

# ... (resto del archivo forms.py, TransaccionForm, CuentaForm, etc.)

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model() # Obtiene el modelo de Usuario activo (django.contrib.auth.models.User)

class RegistroUsuarioForm(UserCreationForm):
    # Aquí puedes añadir campos adicionales si tu modelo de usuario los tuviera.
    # Por ahora, solo usamos los campos predeterminados (username, password, password2).
    
    class Meta(UserCreationForm.Meta):
        # ⚠️ CRÍTICO: El nombre de la clase es RegistroUsuarioForm
        model = User
        fields = UserCreationForm.Meta.fields + ('email',) # Opcional: añade el email
    
    # Opcional: Aplicar estilos Bootstrap a los campos (mejora la apariencia)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

from django import forms
from .models import Cuenta # Asumiendo que tienes un modelo Cuenta

class TransferenciaForm(forms.Form):
    # 1. Campo para el monto
    monto = forms.DecimalField(
        label='Monto a transferir',
        min_value=0.01,
        max_digits=10,
        decimal_places=2,
        # Puedes usar widgets aquí, si los necesitas
    )

    # 2. Campo para la cuenta de origen (queryset limitado a las cuentas del usuario)
    cuenta_origen = forms.ModelChoiceField(
        queryset=Cuenta.objects.all(), # ¡Asegúrate de filtrar por usuario en la vista!
        label='Cuenta de Origen',
        empty_label=None
    )

    # 3. Campo para la cuenta de destino (queryset limitado)
    cuenta_destino = forms.ModelChoiceField(
        queryset=Cuenta.objects.all(), # ¡Asegúrate de filtrar por usuario en la vista!
        label='Cuenta de Destino',
        empty_label=None
    )

    # 4. Campo de descripción (opcional)
    descripcion = forms.CharField(max_length=255, required=False)

    # Opcional: Puedes añadir un método clean para asegurar que origen != destino
    # def clean(self):
    #     # ... lógica de validación ...
