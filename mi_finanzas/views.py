from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView 
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm 
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, DecimalField # Importar DecimalField para seguridad
from django.db.models.functions import Coalesce
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal # <--- NUEVA IMPORTACIÓN PARA SOLUCIONAR EL ERROR DE TIPO

# ========================================================
# 🔑 IMPORTACIONES CONSOLIDADAS DE MODELOS Y FORMULARIOS
# ========================================================
from .models import Cuenta, Transaccion, Presupuesto, Categoria 
from .forms import TransferenciaForm, TransaccionForm, CuentaForm, PresupuestoForm, CategoriaForm 


# ========================================================
# VISTAS DE AUTENTICACIÓN
# ========================================================

class RegistroUsuario(CreateView):
    """Vista para el registro de nuevos usuarios."""
    form_class = UserCreationForm 
    success_url = reverse_lazy('auth:login') 
    template_name = 'registration/signup.html' 

# ========================================================
# VISTAS DE LISTAS Y RESUMEN (Dashboard)
# ========================================================

@login_required
def resumen_financiero(request):
    """Muestra el resumen financiero principal (Dashboard)."""
    cuentas = Cuenta.objects.filter(usuario=request.user)
    
    # Cálculo simple del saldo total
    # CORRECCIÓN: Usar Decimal(0) para evitar la mezcla de Decimal/Float
    saldo_total = cuentas.aggregate(total=Coalesce(Sum('saldo'), Decimal(0)))['total'] 
    
    # Obtener el presupuesto activo (ejemplo)
    presupuestos_activos = Presupuesto.objects.filter(
        usuario=request.user, 
        # Si Presupuesto no tiene estos campos, debes comentar estas líneas:
        # fecha_inicio__lte=date.today(),
        # fecha_fin__gte=date.today()
    ).first()
    
    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'cuentas': cuentas,
        'saldo_total': saldo_total,
        'presupuesto_activo': presupuestos_activos,
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
        return Cuenta.objects.filter(usuario=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = TransferenciaForm(user=self.request.user)
        return context

@method_decorator(login_required, name='dispatch')
class TransaccionesListView(ListView):
    """Muestra la lista de transacciones del usuario."""
    model = Transaccion 
    template_name = 'mi_finanzas/transacciones_lista.html' 
    context_object_name = 'transacciones'

    def get_queryset(self):
        # Filtra las transacciones solo para el usuario actual y las ordena por fecha
        return Transaccion.objects.filter(usuario=self.request.user).order_by('-fecha', '-hora')

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
# VISTAS DE CUENTAS (CRUD)
# ========================================================

@login_required
def anadir_cuenta(request):
    """Vista para añadir una nueva cuenta de forma funcional."""
    if request.method == 'POST':
        form = CuentaForm(request.POST) 
        if form.is_valid():
            cuenta = form.save(commit=False)
            cuenta.usuario = request.user 
            cuenta.save()
            messages.success(request, "¡Cuenta añadida con éxito!")
            return redirect('mi_finanzas:cuentas_lista') 
    else:
        form = CuentaForm()

    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'form': transferencia_form,  # Formulario de transferencia
        'cuenta_form': form         # Formulario principal para añadir la cuenta
    }

    return render(request, 'mi_finanzas/anadir_cuenta.html', context)

@login_required
def editar_cuenta(request, pk):
    """Vista para editar una cuenta existente."""
    cuenta = get_object_or_404(Cuenta, pk=pk, usuario=request.user)

    if request.method == 'POST':
        form = CuentaForm(request.POST, instance=cuenta) 
        if form.is_valid():
            form.save()
            messages.success(request, f"La cuenta '{cuenta.nombre}' ha sido actualizada.")
            return redirect('mi_finanzas:cuentas_lista') 
    else:
        form = CuentaForm(instance=cuenta)

    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'form': transferencia_form,  # Formulario de transferencia
        'cuenta_form': form,         # Formulario principal para editar
        'cuenta': cuenta
    }

    return render(request, 'mi_finanzas/editar_cuenta.html', context)

@login_required
@transaction.atomic
def eliminar_cuenta(request, pk):
    """Vista para eliminar una cuenta existente."""
    cuenta = get_object_or_404(Cuenta, pk=pk, usuario=request.user)

    if request.method == 'POST':
        if cuenta.saldo != 0:
            messages.error(request, f"No se puede eliminar la cuenta '{cuenta.nombre}' porque su saldo no es cero.")
            return redirect('mi_finanzas:cuentas_lista')
            
        nombre_cuenta = cuenta.nombre 
        cuenta.delete()
        messages.success(request, f"La cuenta '{nombre_cuenta}' ha sido eliminada con éxito.")
        return redirect('mi_finanzas:cuentas_lista')
    
    # Si es GET, mostrar formulario de confirmación
    return render(request, 'mi_finanzas/eliminar_cuenta_confirm.html', {'cuenta': cuenta}) 

# ========================================================
# VISTAS DE TRANSACCIONES (CRUD)
# ========================================================

@login_required
def anadir_transaccion(request):
    """Vista para añadir una nueva transacción."""
    if request.method == 'POST':
        # Necesitamos el usuario para filtrar las cuentas en el formulario
        form = TransaccionForm(request.POST, user=request.user) 
        if form.is_valid():
            transaccion = form.save(commit=False)
            transaccion.usuario = request.user
            
            # Ajustar saldo de la cuenta
            cuenta = transaccion.cuenta
            cuenta.saldo += transaccion.monto # Si es egreso, monto es negativo, por lo que resta
            cuenta.save()
            
            transaccion.save()
            messages.success(request, "¡Transacción añadida con éxito!")
            return redirect('mi_finanzas:transacciones_lista')
    else:
        form = TransaccionForm(user=request.user)

    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'form': transferencia_form,
        'transaccion_form': form,
    }
    return render(request, 'mi_finanzas/anadir_transaccion.html', context)


@login_required
@transaction.atomic
def editar_transaccion(request, pk):
    """Vista para editar una transacción existente."""
    transaccion_antigua = get_object_or_404(Transaccion, pk=pk, usuario=request.user)
    monto_original = transaccion_antigua.monto
    
    if request.method == 'POST':
        # Usamos el argumento user para filtrar cuentas en el formulario
        form = TransaccionForm(request.POST, instance=transaccion_antigua, user=request.user) 
        
        if form.is_valid():
            transaccion_nueva = form.save(commit=False)
            monto_nuevo = transaccion_nueva.monto
            
            # Lógica de ajuste de saldos (CRÍTICA)
            cuenta = transaccion_antigua.cuenta
            
            # 1. Deshacer el impacto del monto original
            cuenta.saldo -= monto_original
            
            # 2. Aplicar el impacto del monto nuevo
            cuenta.saldo += monto_nuevo
            
            # 3. Guardar los cambios
            cuenta.save()
            transaccion_nueva.save() 
            
            messages.success(request, "¡Transacción actualizada con éxito!")
            return redirect('mi_finanzas:transacciones_lista') 
    else:
        form = TransaccionForm(instance=transaccion_antigua, user=request.user)

    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'form': transferencia_form,
        'transaccion_form': form,
        'transaccion': transaccion_antigua
    }

    return render(request, 'mi_finanzas/editar_transaccion.html', context)


@login_required
@transaction.atomic
def eliminar_transaccion(request, pk):
    """Vista para eliminar una transacción y revertir su efecto en el saldo de la cuenta."""
    transaccion = get_object_or_404(Transaccion, pk=pk, usuario=request.user)
    
    if request.method == 'POST':
        cuenta = transaccion.cuenta
        monto = transaccion.monto 
        
        # Lógica de Reversión: Restamos el impacto (si era -50 (egreso), restar -50 es sumar 50)
        cuenta.saldo -= monto
        
        cuenta.save()
        transaccion.delete()
        
        messages.success(request, "¡Transacción eliminada y saldo ajustado con éxito!")
        return redirect('mi_finanzas:transacciones_lista')
    
    context = {
        'transaccion': transaccion
    }
    return render(request, 'mi_finanzas/eliminar_transaccion_confirm.html', context)


# ========================================================
# VISTAS DE PRESUPUESTOS (CRUD)
# ========================================================

@method_decorator(login_required, name='dispatch')
class PresupuestosListView(ListView):
    """Muestra la lista de presupuestos del usuario."""
    model = Presupuesto 
    template_name = 'mi_finanzas/presupuestos_lista.html' 
    context_object_name = 'presupuestos'

    def get_queryset(self):
        # Ordenar por fecha de inicio descendente
        return Presupuesto.objects.filter(usuario=self.request.user).order_by('-fecha_inicio')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = TransferenciaForm(user=self.request.user)
        return context


@login_required
def crear_presupuesto(request):
    """Vista para crear un nuevo presupuesto."""
    if request.method == 'POST':
        form = PresupuestoForm(request.POST, user=request.user) 
        if form.is_valid():
            presupuesto = form.save(commit=False)
            presupuesto.usuario = request.user
            presupuesto.save()
            # Guardar categorías (asumiendo que PresupuestoForm tiene manejo de categorías)
            form.save_m2m() 
            messages.success(request, "¡Presupuesto creado con éxito!")
            return redirect('mi_finanzas:lista_presupuestos') 
    else:
        form = PresupuestoForm(user=request.user)

    context = {
        'presupuesto_form': form,
        'form': TransferenciaForm(user=request.user),
    }

    return render(request, 'mi_finanzas/crear_presupuesto.html', context)


@login_required
def editar_presupuesto(request, pk):
    """Vista para editar un presupuesto existente."""
    presupuesto = get_object_or_404(Presupuesto, pk=pk, usuario=request.user)

    if request.method == 'POST':
        form = PresupuestoForm(request.POST, instance=presupuesto, user=request.user) 
        if form.is_valid():
            form.save()
            messages.success(request, "¡Presupuesto actualizado con éxito!")
            return redirect('mi_finanzas:lista_presupuestos') 
    else:
        form = PresupuestoForm(instance=presupuesto, user=request.user)

    context = {
        'presupuesto_form': form,
        'presupuesto': presupuesto,
        'form': TransferenciaForm(user=request.user),
    }

    return render(request, 'mi_finanzas/editar_presupuesto.html', context)


@login_required
def eliminar_presupuesto(request, pk):
    """Vista para eliminar un presupuesto existente."""
    presupuesto = get_object_or_404(Presupuesto, pk=pk, usuario=request.user)

    if request.method == 'POST':
        # Nota: Asumo que Presupuesto tiene un campo 'nombre'
        nombre_presupuesto = presupuesto.nombre
        presupuesto.delete()
        messages.success(request, f"El presupuesto '{nombre_presupuesto}' ha sido eliminado.")
        return redirect('mi_finanzas:lista_presupuestos')
    
    return render(request, 'mi_finanzas/eliminar_presupuesto_confirm.html', {'presupuesto': presupuesto})


# ========================================================
# VISTAS DE REPORTES
# ========================================================

@login_required
def reportes_financieros(request):
    """Vista principal para mostrar diferentes tipos de reportes."""
    
    # 1. Calcular rango de fechas (ejemplo: últimos 6 meses)
    hoy = date.today()
    fecha_inicio = hoy - relativedelta(months=5)
    
    # 2. Obtener transacciones filtradas
    transacciones = Transaccion.objects.filter(
        usuario=request.user, 
        fecha__gte=fecha_inicio
    ).order_by('fecha')
    
    # 3. Total de Ingresos y Egresos en el rango
    # CORRECCIÓN: Usar Decimal(0) y especificar output_field=DecimalField() 
    # para evitar el error de tipos mixtos (DecimalField con 0/int/float).
    totales = transacciones.aggregate(
        ingresos=Coalesce(Sum('monto', filter='monto__gt=0'), Decimal(0), output_field=DecimalField()),
        egresos=Coalesce(Sum('monto', filter='monto__lt=0'), Decimal(0), output_field=DecimalField())
    )
    
    context = {
        'transacciones': transacciones,
        'totales': totales,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': hoy,
        'form': TransferenciaForm(user=request.user), # Para el modal
    }
    
    return render(request, 'mi_finanzas/reportes_financieros.html', context)
