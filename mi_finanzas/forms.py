from django import forms
from .models import Cuenta, Transaccion, Categoria, Presupuesto
from django.forms.widgets import TextInput, NumberInput, Select, Textarea, DateInput
from django.utils import timezone
import calendar 
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model() 

# ----------------------------------------------------
# 1. Formulario de Cuentas (CRUD)
# ----------------------------------------------------

class CuentaForm(forms.ModelForm):
    class Meta:
        model = Cuenta
        fields = ['nombre', 'tipo', 'balance'] 
        widgets = {
            'nombre': TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Banco Principal'}),
            'tipo': Select(attrs={'class': 'form-select'}), 
            'balance': NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
        }

# ----------------------------------------------------
# 2. Formulario de Transacciones (CRUD)
# ----------------------------------------------------

class TransaccionForm(forms.ModelForm):
    # Sobrescribe la fecha para asegurar el widget HTML5 type='date'
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    # CRÍTICO: Constructor para filtrar Cuentas y Categorías por Usuario
    def __init__(self, *args, **kwargs):
        # 1. Interceptamos 'solicitar' si viene de la vista
        request = kwargs.pop('solicitar', None) 
        
        # 2. Interceptamos 'request' si se pasó (para más robustez)
        if request is None:
            request = kwargs.pop('request', None)
        
        # 3. Mantenemos el soporte para pasar 'user' directamente (opcional)
        user = kwargs.pop('user', None) 
        
        # 4. Llamada al constructor base SIN las claves personalizadas
        super().__init__(*args, **kwargs) 

        # 5. Determinar el usuario si no se pasó directamente
        if user is None and request and request.user.is_authenticated:
            user = request.user

        if user is not None:
            # Filtra Cuentas y Categorías del usuario
            self.fields['cuenta'].queryset = Cuenta.objects.filter(usuario=user)
            self.fields['categoria'].queryset = Categoria.objects.filter(usuario=user)

            # Aplica estilos a los Select
            self.fields['cuenta'].widget.attrs.update({'class': 'form-select'})
            self.fields['categoria'].widget.attrs.update({'class': 'form-select'})

    class Meta:
        model = Transaccion
        fields = ['monto', 'tipo', 'categoria', 'fecha', 'descripcion', 'cuenta']
        widgets = {
            'monto': NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'tipo': Select(attrs={'class': 'form-select'}),
            'descripcion': Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

# ----------------------------------------------------
# 3. Formulario de Transferencia (Custom Form)
# ----------------------------------------------------

class TransferenciaForm(forms.Form):
    # Definiciones de campos (sin queryset inicial)
    cuenta_origen = forms.ModelChoiceField(
        queryset=Cuenta.objects.none(), # Se inicializa a none
        label="Cuenta de Origen",
        empty_label="Selecciona una cuenta..."
    )
    cuenta_destino = forms.ModelChoiceField(
        queryset=Cuenta.objects.none(), # Se inicializa a none
        label="Cuenta de Destino",
        empty_label="Selecciona una cuenta..."
    )
    monto = forms.DecimalField(
        label='Monto a transferir',
        min_value=0.01,
        max_digits=10,
        decimal_places=2,
        widget=NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '100.00'})
    )
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    descripcion = forms.CharField(
        max_length=255, 
        required=False, 
        widget=TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Ahorros a Inversión'})
    )

    # EL CONSTRUCTOR CRÍTICO para filtrar Cuentas por Usuario
    def __init__(self, *args, **kwargs):
        # 1. Interceptamos 'solicitar' si viene de la vista
        request = kwargs.pop('solicitar', None)
        
        # 2. Interceptamos 'request' si se pasó (para más robustez)
        if request is None:
            request = kwargs.pop('request', None)

        # 3. Mantenemos el soporte para pasar 'user' directamente (opcional)
        user = kwargs.pop('user', None) 
        
        # 4. Llamada al constructor base SIN las claves personalizadas
        super().__init__(*args, **kwargs) 

        # 5. Determinar el usuario si no se pasó directamente
        if user is None and request and request.user.is_authenticated:
            user = request.user

        if user is not None:
            cuentas_del_usuario = Cuenta.objects.filter(usuario=user)
            self.fields['cuenta_origen'].queryset = cuentas_del_usuario
            self.fields['cuenta_destino'].queryset = cuentas_del_usuario
            
        # Aplicar estilo Bootstrap a los ModelChoiceFields
        self.fields['cuenta_origen'].widget.attrs.update({'class': 'form-select'})
        self.fields['cuenta_destino'].widget.attrs.update({'class': 'form-select'})
        
    # Lógica de validación: Las cuentas no pueden ser la misma
    def clean(self):
        cleaned_data = super().clean()
        origen = cleaned_data.get('cuenta_origen')
        destino = cleaned_data.get('cuenta_destino')

        if origen and destino and origen == destino:
            raise forms.ValidationError(
                "La cuenta de origen y la cuenta de destino no pueden ser la misma."
            )
        return cleaned_data

# ----------------------------------------------------
# 4. Formulario de Presupuestos (CRUD)
# ----------------------------------------------------

hoy = timezone.localdate()
MESES_CHOICES = [(i, calendar.month_name[i].capitalize()) for i in range(1, 13)]
ANIO_CHOICES = [(y, y) for y in range(hoy.year, hoy.year + 5)]

class PresupuestoForm(forms.ModelForm):
    # Sobrescribe los campos Mes y Año
    mes = forms.TypedChoiceField(
        choices=MESES_CHOICES,
        coerce=int,
        initial=hoy.month, 
        label="Mes del Presupuesto",
        widget=Select(attrs={'class': 'form-select'}) 
    )
    anio = forms.TypedChoiceField(
        choices=ANIO_CHOICES,
        coerce=int,
        initial=hoy.year, 
        label="Año del Presupuesto",
        widget=Select(attrs={'class': 'form-select'}) 
    )
    
    class Meta:
        model = Presupuesto
        fields = ('categoria', 'monto_limite', 'mes', 'anio')
        widgets = {
            'monto_limite': NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': 'Ej: 500.00'}),
        }
        
    # CRÍTICO: Constructor para filtrar Categorías por Usuario
    def __init__(self, *args, **kwargs):
        # 1. Interceptamos 'solicitar' si viene de la vista (versión en español)
        request = kwargs.pop('solicitar', None) 

        # 2. Interceptamos 'request' si se pasó (versión en inglés) <--- ¡CORRECCIÓN CLAVE!
        if request is None: 
            request = kwargs.pop('request', None)

        # 3. Mantenemos el soporte para pasar 'user' directamente (opcional)
        user = kwargs.pop('user', None) 
        
        # 4. Llamada al constructor base SIN las claves personalizadas
        super().__init__(*args, **kwargs)
        
        # 5. Determinar el usuario para el filtrado
        if user is None and request and request.user.is_authenticated:
            user = request.user
        
        if user is not None:
            self.fields['categoria'].queryset = Categoria.objects.filter(usuario=user)
            self.fields['categoria'].widget.attrs.update({'class': 'form-select'}) # Aplica estilo

# ----------------------------------------------------
# 5. Formulario de Login y Registro
# ----------------------------------------------------

class LoginForm(forms.Form):
    username = forms.CharField(
        label='Nombre de usuario',
        max_length=150,
        widget=TextInput(attrs={'class': 'form-control', 'placeholder': 'Usuario'})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'})
    )

class RegistroUsuarioForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',) 
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

