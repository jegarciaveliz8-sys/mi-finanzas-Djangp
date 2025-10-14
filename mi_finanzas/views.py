from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView # Añadido CreateView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm # Añadido UserCreationForm
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum

# Importaciones de Modelos y Formularios (Ajusta según tus nombres reales)
from .models import Cuenta, Transaccion
from .forms import TransferenciaForm, TransaccionForm 

# ========================================================
# VISTAS DE AUTENTICACIÓN
# ========================================================

# 🔑 ESTO RESUELVE EL IMPORTERROR
class RegistroUsuario(CreateView):
    """Vista para el registro de nuevos usuarios."""
    # Utiliza el formulario básico de creación de usuario de Django
    form_class = UserCreationForm 
    
    # Redirige al login después de un registro exitoso
    success_url = reverse_lazy('auth:login') 
    
    # Especifica la plantilla para el formulario de registro
    template_name = 'registration/signup.html' 

# ========================================================
# VISTAS DE LISTAS Y RESUMEN
# ========================================================

@login_required
def resumen_financiero(request):
    """Muestra el resumen financiero principal."""
    cuentas = Cuenta.objects.filter(usuario=request.user)
    
    # Cálculo simple del saldo total
    saldo_total = cuentas.aggregate(total=Sum('saldo'))['total'] or 0.00
    
    # PASO CLAVE: Instanciar y añadir el formulario de transferencia para el modal
    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'cuentas': cuentas,
        'saldo_total': saldo_total,
        'form': transferencia_form,  # ¡Inyectado para el modal!
    }
    return render(request, 'mi_finanzas/resumen_financiero.html', context)


@method_decorator(login_required, name='dispatch')
class CuentasListView(ListView):
    """Muestra la lista de cuentas del usuario."""
    model = Cuenta
    template_name = 'mi_finanzas/cuentas_lista.html'
    context_object_name = 'cuentas'

    def get_queryset(self):
        # Asegura que solo se muestren las cuentas del usuario actual
        return Cuenta.objects.filter(usuario=self.request.user)

    def get_context_data(self, **kwargs):
        # Llama a la implementación base
        context = super().get_context_data(**kwargs)
        
        # PASO CLAVE: Inyectar la instancia del formulario de transferencia.
        context['form'] = TransferenciaForm(user=self.request.user)
        
        return context

# ========================================================
# VISTA DE TRANSFERENCIA (Lógica de Negocio)
# ========================================================

@login_required
@transaction.atomic
def transferir_monto(request):
    """Maneja la lógica para transferir fondos entre cuentas."""
    if request.method == 'POST':
        form = TransferenciaForm(request.user, request.POST)
        
        if form.is_valid():
            cuenta_origen = form.cleaned_data['cuenta_origen']
            cuenta_destino = form.cleaned_data['cuenta_destino']
            monto = form.cleaned_data['monto']

            if cuenta_origen.saldo < monto:
                messages.error(request, 'Saldo insuficiente en la cuenta de origen.')
                return redirect('mi_finanzas:resumen_financiero')

            # Actualizar saldos y registrar transacciones
            cuenta_origen.saldo -= monto
            cuenta_destino.saldo += monto
            
            cuenta_origen.save()
            cuenta_destino.save()

            Transaccion.objects.create(
                usuario=request.user, cuenta=cuenta_origen, tipo='EGRESO', monto=-monto,
                descripcion=f"Transferencia a {cuenta_destino.nombre}",
            )
            Transaccion.objects.create(
                usuario=request.user, cuenta=cuenta_destino, tipo='INGRESO', monto=monto,
                descripcion=f"Transferencia desde {cuenta_origen.nombre}",
            )

            messages.success(request, '¡Transferencia realizada con éxito!')
            return redirect('mi_finanzas:resumen_financiero')
        
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error en {field}: {error}")
            
    return redirect('mi_finanzas:resumen_financiero')

# ========================================================
# VISTAS VARIAS (Ejemplo de inyección de formulario)
# ========================================================

@login_required
def anadir_transaccion(request):
    """Ejemplo de otra vista que debe inyectar el form de transferencia."""
    
    # Asegurando el modal de transferencia aquí también
    transferencia_form = TransferenciaForm(user=request.user)

    context = {
        'transaccion_form': TransaccionForm(),
        'form': transferencia_form, # ¡Inyectado!
    }
    return render(request, 'mi_finanzas/anadir_transaccion.html', context)


@method_decorator(login_required, name='dispatch')
class TransaccionesListView(ListView):
    """Muestra la lista de transacciones del usuario."""
    model = Transaccion 
    template_name = 'mi_finanzas/transacciones_lista.html' 
    context_object_name = 'transacciones'

    def get_queryset(self):
        # Filtra las transacciones solo para el usuario actual y las ordena por fecha
        return Transaccion.objects.filter(usuario=self.request.user).order_by('-fecha')

# ... (Si tuvieras más código) ...



from .models import Cuenta  # Asegúrate de que el modelo Cuenta esté importado
from .forms import CuentaForm # Necesitas un formulario para crear/añadir cuentas
from django.urls import reverse_lazy

@login_required
def anadir_cuenta(request):
    """Vista para añadir una nueva cuenta de forma funcional."""
    if request.method == 'POST':
        # Asume que tienes un formulario llamado CuentaForm
        form = CuentaForm(request.POST) 
        if form.is_valid():
            cuenta = form.save(commit=False)
            cuenta.usuario = request.user # Asigna la cuenta al usuario logueado
            cuenta.save()
            messages.success(request, "¡Cuenta añadida con éxito!")
            # Redirige a la lista de cuentas
            return redirect('mi_finanzas:cuentas_lista') 
    else:
        form = CuentaForm()

    # Inyecta el formulario de transferencia para el modal de base.html (IMPORTANTE)
    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'form': transferencia_form,  # Formulario de transferencia
        'cuenta_form': form         # Formulario principal para añadir la cuenta
    }

    # Asume que tienes una plantilla para este formulario
    return render(request, 'mi_finanzas/anadir_cuenta.html', context)


from django.shortcuts import get_object_or_404 # Asegúrate de que esta importación esté al inicio
from django.contrib import messages
from django.shortcuts import redirect
# Asegúrate de importar Cuenta, CuentaForm y TransferenciaForm

@login_required
def editar_cuenta(request, pk):
    """Vista para editar una cuenta existente."""
    # 1. Recuperar la cuenta o devolver 404 si no existe
    # Asegúrate de que solo se editen las cuentas del usuario actual
    cuenta = get_object_or_404(Cuenta, pk=pk, usuario=request.user)

    if request.method == 'POST':
        # 2. Rellenar el formulario con los datos POST y la instancia de la cuenta
        form = CuentaForm(request.POST, instance=cuenta) 
        if form.is_valid():
            form.save()
            messages.success(request, f"La cuenta '{cuenta.nombre}' ha sido actualizada.")
            return redirect('mi_finanzas:cuentas_lista') 
    else:
        # 3. Mostrar el formulario precargado con los datos de la cuenta
        form = CuentaForm(instance=cuenta)

    # 4. Inyectar el formulario de transferencia para el modal (siempre necesario)
    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'form': transferencia_form,  # Formulario de transferencia
        'cuenta_form': form,         # Formulario principal para editar
        'cuenta': cuenta
    }

    # Asume que tienes una plantilla llamada 'mi_finanzas/editar_cuenta.html'
    return render(request, 'mi_finanzas/editar_cuenta.html', context)

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction # Recomendado para operaciones de eliminación sensibles
# Asegúrate de importar Cuenta

@login_required
@transaction.atomic
def eliminar_cuenta(request, pk):
    """Vista para eliminar una cuenta existente."""
    # 1. Recuperar la cuenta o devolver 404
    cuenta = get_object_or_404(Cuenta, pk=pk, usuario=request.user)

    if request.method == 'POST':
        # 2. Verificar que el saldo sea cero antes de eliminar (Buena práctica de negocio)
        if cuenta.saldo != 0:
            messages.error(request, f"No se puede eliminar la cuenta '{cuenta.nombre}' porque su saldo no es cero. Transfiere los fondos primero.")
            return redirect('mi_finanzas:cuentas_lista')
            
        # 3. Si el saldo es cero, eliminar la cuenta
        nombre_cuenta = cuenta.nombre # Guardamos el nombre antes de la eliminación
        cuenta.delete()
        messages.success(request, f"La cuenta '{nombre_cuenta}' ha sido eliminada con éxito.")
        return redirect('mi_finanzas:cuentas_lista')
    
    # 4. Si es GET, simplemente se debería mostrar un formulario de confirmación 
    # (aunque si se accede directamente por POST, funciona)
    # Asume que tienes una plantilla para la confirmación
    return render(request, 'mi_finanzas/eliminar_cuenta_confirm.html', {'cuenta': cuenta}) 


from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
# Asegúrate de que los modelos y formularios (Transaccion, TransaccionForm) estén importados

@login_required
@transaction.atomic
def editar_transaccion(request, pk):
    """Vista para editar una transacción existente."""
    # 1. Recuperar la transacción o devolver 404
    transaccion_antigua = get_object_or_404(Transaccion, pk=pk, usuario=request.user)
    
    # Guardamos el monto original de la transacción antes de cualquier cambio.
    monto_original = transaccion_antigua.monto
    
    if request.method == 'POST':
        # 2. Rellenar el formulario con los datos POST y la instancia de la transacción antigua
        # Asume que tienes un formulario llamado TransaccionForm
        form = TransaccionForm(request.POST, instance=transaccion_antigua) 
        
        if form.is_valid():
            # 3. Guardar la nueva transacción (aún sin persistir en la DB)
            transaccion_nueva = form.save(commit=False)
            monto_nuevo = transaccion_nueva.monto
            
            # Lógica de ajuste de saldos (CRÍTICA)
            # a. Deshacer el impacto del monto original en la cuenta
            cuenta = transaccion_antigua.cuenta
            cuenta.saldo += monto_original
            
            # b. Aplicar el impacto del monto nuevo en la cuenta
            cuenta.saldo -= monto_nuevo # Si el monto es negativo, se convierte en suma
            
            # 4. Guardar los cambios
            cuenta.save()
            transaccion_nueva.save() # Guarda la transacción actualizada
            
            messages.success(request, "¡Transacción actualizada con éxito!")
            return redirect('mi_finanzas:transacciones_lista') 
    else:
        # 5. Mostrar el formulario precargado con los datos de la transacción
        form = TransaccionForm(instance=transaccion_antigua)

    # 6. Inyectar el formulario de transferencia para el modal de base.html
    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'form': transferencia_form,       # Formulario de transferencia
        'transaccion_form': form,         # Formulario principal para editar
        'transaccion': transaccion_antigua
    }

    # Asume que tienes una plantilla para este formulario
    return render(request, 'mi_finanzas/editar_transaccion.html', context)
