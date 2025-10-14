from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum

# Importaciones de Modelos y Formularios (Ajusta según tus nombres reales)
from .models import Cuenta, Transaccion
from .forms import TransferenciaForm, TransaccionForm 

# ========================================================
# VISTAS DE LISTAS Y RESUMEN (Asegurando el Formulario en el Contexto)
# ========================================================

@login_required
def resumen_financiero(request):
    """Muestra el resumen financiero principal."""
    cuentas = Cuenta.objects.filter(usuario=request.user)
    
    # Cálculo simple del saldo total
    saldo_total = cuentas.aggregate(total=Sum('saldo'))['total'] or 0.00
    
    # 🔑 PASO CLAVE: Instanciar y añadir el formulario de transferencia
    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'cuentas': cuentas,
        'saldo_total': saldo_total,
        'form': transferencia_form,  # ¡Inyectado para el modal en base.html!
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
        # Llama a la implementación base para obtener el contexto predeterminado
        context = super().get_context_data(**kwargs)
        
        # 🔑 PASO CLAVE: Inyectar la instancia del formulario de transferencia
        # Esto soluciona el TypeError en el modal de base.html
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
        # La vista siempre debe pasar el usuario al formulario para filtrar cuentas
        form = TransferenciaForm(request.user, request.POST)
        
        if form.is_valid():
            cuenta_origen = form.cleaned_data['cuenta_origen']
            cuenta_destino = form.cleaned_data['cuenta_destino']
            monto = form.cleaned_data['monto']

            if cuenta_origen.saldo < monto:
                messages.error(request, 'Saldo insuficiente en la cuenta de origen.')
                return redirect('mi_finanzas:resumen_financiero')

            # 1. Actualizar saldos de cuentas
            cuenta_origen.saldo -= monto
            cuenta_destino.saldo += monto
            
            cuenta_origen.save()
            cuenta_destino.save()

            # 2. Registrar las transacciones (Opcional, pero recomendado)
            Transaccion.objects.create(
                usuario=request.user,
                cuenta=cuenta_origen,
                tipo='EGRESO',
                monto=-monto,
                descripcion=f"Transferencia a {cuenta_destino.nombre}",
                # otros campos si los tienes
            )
            Transaccion.objects.create(
                usuario=request.user,
                cuenta=cuenta_destino,
                tipo='INGRESO',
                monto=monto,
                descripcion=f"Transferencia desde {cuenta_origen.nombre}",
                # otros campos si los tienes
            )

            messages.success(request, '¡Transferencia realizada con éxito!')
            return redirect('mi_finanzas:resumen_financiero')
        
        else:
            # Si el formulario no es válido, generalmente se re-renderiza la página
            # En el caso de un modal, es mejor redirigir y mostrar errores
            # (En un proyecto real, se manejaría con AJAX)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error en {field}: {error}")
            
    # Redirigir a una vista que cargue el formulario no válido para mostrar errores
    return redirect('mi_finanzas:resumen_financiero')

# ========================================================
# VISTAS DE TRANSACCIONES (Ejemplo)
# ========================================================

# Aquí irían las vistas para transacciones, editar cuentas, etc.
# Si añades un formulario en estas vistas, recuerda inyectar el TransferenciaForm:

@login_required
def anadir_transaccion(request):
    # ... Lógica de la vista para añadir una transacción ...
    
    # 🔑 Asegurando el modal de transferencia aquí también
    transferencia_form = TransferenciaForm(user=request.user)

    context = {
        'transaccion_form': TransaccionForm(),
        'form': transferencia_form, # ¡Inyectado!
    }
    return render(request, 'mi_finanzas/anadir_transaccion.html', context)
