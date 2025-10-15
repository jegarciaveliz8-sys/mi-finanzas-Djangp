from django import forms
from django.forms.widgets import TextInput, NumberInput, Select, Textarea, DateInput
from django.utils import timezone
import calendar 
from django.contrib.auth import get_user_model
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Fieldset # Agregué Fieldset para agrupar

# Importaciones de Modelos (Asegúrate de que estos modelos existan en models.py)
from .models import Cuenta, Transaccion, Categoria, Presupuesto 

User = get_user_model() 

# ----------------------------------------------------
# 1. Formulario de Cuentas (CRUD)
# ----------------------------------------------------

class CuentaForm(forms.ModelForm):
    class Meta:
        model = Cuenta
        # Usando 'saldo' tal como se corrigió previamente.
        fields = ['nombre', 'tipo', 'saldo'] 
        widgets = {
            'nombre': TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Banco Principal'}),
            'tipo': Select(attrs={'class': 'form-select'}), 
            'saldo': NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
        }

# ----------------------------------------------------
# 2. Formulario de Transacciones (CRUD)
# ----------------------------------------------------

class TransaccionForm(forms.ModelForm):
    # Sobrescribe la fecha para asegurar el widget HTML5 type='date'
    fecha = forms.DateField(
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )




    
     def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        user = kwargs.pop('user', None) 
        
        super().__init__(*args, **kwargs) 
 

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
    cuenta_origen = forms.ModelChoiceField(
        queryset=Cuenta.objects.none(),
        label="Cuenta de Origen",
        empty_label="Selecciona una cuenta..."
    )
    cuenta_destino = forms.ModelChoiceField(
        queryset=Cuenta.objects.none(),
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
    # ✅ CORRECCIÓN/ADICIÓN: Se añade el widget de fecha para asegurar el input de calendario.
    fecha = forms.DateField(
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control', 'value': timezone.localdate()})
    )
    descripcion = forms.CharField(
        max_length=255, 
        required=False, 
        widget=TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Ahorros a Inversión'})
    )

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        user = kwargs.pop('user', None) 
        
        super().__init__(*args, **kwargs) 

        if user is None and request and request.user.is_authenticated:
            user = request.user

        if user is not None:
            cuentas_del_usuario = Cuenta.objects.filter(usuario=user)
            self.fields['cuenta_origen'].queryset = cuentas_del_usuario
            self.fields['cuenta_destino'].queryset = cuentas_del_usuario
        
        # Aplicación de estilos para Select
        self.fields['cuenta_origen'].widget.attrs.update({'class': 'form-select'})
        self.fields['cuenta_destino'].widget.attrs.update({'class': 'form-select'})
        
        # Inicializa la fecha con el día actual si no se está cargando data (instance)
        if not self.is_bound:
            self.fields['fecha'].initial = timezone.localdate()

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
# 4. Formulario de Presupuestos (Creación)
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
        
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None) 
        user = kwargs.pop('user', None) 
        
        super().__init__(*args, **kwargs)
        
        if user is None and request and request.user.is_authenticated:
            user = request.user
        
        if user is not None:
            self.fields['categoria'].queryset = Categoria.objects.filter(usuario=user)
            self.fields['categoria'].widget.attrs.update({'class': 'form-select'})

# ----------------------------------------------------
# 5. Formulario de Categorías (CRUD)
# ----------------------------------------------------

class CategoriaForm(forms.ModelForm):
    """Formulario para la creación y edición de categorías."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicar estilo Bootstrap a los campos
        for field in self.fields.values():
            if field.widget.__class__ in [Select, forms.Select]:
                field.widget.attrs.update({'class': 'form-select'})
            elif field.widget.__class__ in [TextInput, forms.TextInput]:
                field.widget.attrs.update({'class': 'form-control'})

    class Meta:
        model = Categoria
        fields = ('nombre', 'tipo') 
        
        widgets = {
            'nombre': TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Alimentación'}),
            'tipo': Select(attrs={'class': 'form-select'}),
        }

