from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, DecimalField, F
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy 
from django.views.generic import CreateView 
from django.contrib.auth.models import User 
from django.views.decorators.http import require_POST 
from django.db import transaction, IntegrityError 
from django.utils import timezone 

import json
import datetime
from decimal import Decimal

# Importaciones Locales CRÍTICAS:
from .models import Cuenta, Transaccion, Categoria, Presupuesto
from .forms import (
    RegistroUsuarioForm, 
    TransaccionForm, 
    TransferenciaForm, 
    CuentaForm, 
    PresupuestoForm,
    # Asegúrate de que este formulario exista en forms.py
    # PresupuestoUpdateForm 
)


# =========================================================
# 0. VISTA DE REGISTRO DE USUARIO
# =========================================================

class RegistroUsuario(CreateView):
    """
    Vista basada en clase para el registro de nuevos usuarios.
    """
    model = User
    form_class = RegistroUsuarioForm
    template_name = 'mi_finanzas/registro.html'
    success_url = reverse_lazy('mi_finanzas:resumen_financiero') 


# =========================================================
# 1. VISTA DE RESUMEN (PANEL DE CONTROL) - ¡CORREGIDA!
# =========================================================
<button type="button" class="btn btn-primary my-3" data-bs-toggle="modal" data-bs-target="#transferModal">
    <i class="fas fa-exchange-alt me-2"></i> Realizar Transferencia
</button>
@login_required
def resumen_financiero(request):
    usuario = request.user
    hoy = timezone.localdate()
    mes_actual = hoy.month
    anio_actual = hoy.year
    
    # QuerySet Base para el mes actual
    transacciones_mes_base = Transaccion.objects.filter(
        usuario=usuario, 
        fecha__month=mes_actual, 
        fecha__year=anio_actual
    )
    
    # --- LÓGICA DE EXCLUSIÓN DE TRANSFERENCIAS (CORRECCIÓN CLAVE) ---
    cats_a_excluir = []
    # Usamos try-except para asegurar que no falle si el usuario no ha hecho una transferencia
    # y las categorías aún no existen.
    try:
        cat_salida = Categoria.objects.get(nombre='Transferencia Salida', usuario=usuario)
        cat_entrada = Categoria.objects.get(nombre='Transferencia Entrada', usuario=usuario)
        cats_a_excluir = [cat_salida.pk, cat_entrada.pk]
    except Categoria.DoesNotExist:
        # Si no existen las categorías de transferencia, no excluimos nada.
        pass


    # --- CÁLCULO DE MÉTRICAS GLOBALES ---
    saldo_total_neto = Cuenta.objects.filter(usuario=usuario).aggregate(
        total=Coalesce(Sum('balance'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    # --- MÉTRICAS MENSUALES (Aplicando la exclusión) ---
    
    # Excluye la Transferencia Entrada para calcular INGRESOS REALES
    ingresos_del_mes = transacciones_mes_base.filter(
        tipo='INGRESO'
    ).exclude(
        categoria__pk__in=cats_a_excluir 
    ).aggregate(
        total=Coalesce(Sum('monto'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    # Excluye la Transferencia Salida para calcular GASTOS REALES
    gastos_del_mes = transacciones_mes_base.filter(
        tipo='GASTO'
    ).exclude(
        categoria__pk__in=cats_a_excluir
    ).aggregate(
        total=Coalesce(Sum('monto'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    # -----------------------------------------------------------------
    # --- LISTA DE CUENTAS ---
    cuentas = Cuenta.objects.filter(usuario=usuario).order_by('nombre')
    
    # --- DATOS PARA GRÁFICO DE GASTOS ---
    # También debemos excluir las transferencias del gráfico para que no distorsione los gastos por categoría
    gastos_por_categoria_qs = transacciones_mes_base.filter(
        tipo='GASTO',
    ).exclude(
        categoria__pk__in=cats_a_excluir
    ).values('categoria__nombre').annotate(
        total=Coalesce(Sum('monto'), Decimal(0.00))
    ).order_by('-total')

    chart_labels = [gasto['categoria__nombre'] if gasto['categoria__nombre'] else 'Sin Categoría' 
                     for gasto in gastos_por_categoria_qs if gasto['total'] > 0]
    chart_data_values = [float(gasto['total']) 
                         for gasto in gastos_por_categoria_qs if gasto['total'] > 0]

    chart_data = {
        'labels': chart_labels,
        'data': chart_data_values
    }
    # Convertimos a JSON para pasar al JavaScript del template
    chart_data_json = json.dumps(chart_data)

    # --- LÓGICA DE PRESUPUESTOS ---
    presupuestos_activos = Presupuesto.objects.filter(
        usuario=usuario, 
        mes=mes_actual, 
        anio=anio_actual
    ).select_related('categoria') 
    
    for presupuesto in presupuestos_activos:
        # Filtramos los gastos del mes por la categoría
        # NOTA: No excluimos aquí porque los presupuestos ya están filtrados por la categoría
        gasto_real = transacciones_mes_base.filter(
            tipo='GASTO',
            categoria=presupuesto.categoria,
        ).aggregate(
            total=Coalesce(Sum('monto'), Decimal(0.00))
        )['total']
        
        limite = presupuesto.monto_limite 
        presupuesto.gasto_actual = gasto_real
        presupuesto.restante = limite - gasto_real
        
        # Cálculo del porcentaje
        if limite > 0:
            porcentaje = (gasto_real / limite) * 100
        else:
            porcentaje = 0
            
        presupuesto.porcentaje = min(porcentaje, 100) # Limitar la barra de progreso visualmente al 100%
        
        # Lógica para el color de la barra (Bootstrap)
        if porcentaje <= 75:
            presupuesto.color_barra = 'bg-success'
        elif porcentaje <= 100:
            presupuesto.color_barra = 'bg-warning'
        else:
            presupuesto.color_barra = 'bg-danger'
            
    # --- ACTIVIDAD RECIENTE (N+1 Resuelto) ---
    # Pedimos 5 transacciones más el par de transferencia (2 más) para asegurar que se muestre.
    ultimas_transacciones = Transaccion.objects.filter(usuario=usuario).select_related(
        'cuenta', 'categoria'
    ).order_by('-fecha')[:7] 
    
    # --- LÓGICA DEL MENSAJE DE SALUD FINANCIERA ---
    if saldo_total_neto > 500: 
        estado_financiero = {
            'tipo': 'alert-success',
            'icono': 'fas fa-thumbs-up',
            'mensaje': '¡Excelente! Tu salud financiera es fuerte. Sigue así.'
        }
    elif saldo_total_neto >= 0:
        estado_financiero = {
            'tipo': 'alert-warning',
            'icono': 'fas fa-exclamation-triangle',
            'mensaje': 'Estás en territorio positivo, pero considera aumentar tus ahorros.'
        }
    else:
        estado_financiero = {
            'tipo': 'alert-danger',
            'icono': 'fas fa-skull-crossbones',
            'mensaje': '¡ATENCIÓN! Tu balance neto es negativo. Revisa tus cuentas.'
        }

    # --- CONTEXTO FINAL ---
    contexto = {
        # Métricas principales
        'saldo_total_neto': saldo_total_neto,
        'ingresos_del_mes': ingresos_del_mes,
        'gastos_del_mes': gastos_del_mes,
        'mes_actual': hoy.strftime('%B'),
        'anio_actual': anio_actual,
        
        # Dashboard Data
        'cuentas': cuentas,
        'ultimas_transacciones': ultimas_transacciones,
        'estado_financiero': estado_financiero,
        
        # Datos de gráficos y presupuestos
        'gastos_por_categoria': gastos_por_categoria_qs,
        'chart_data_json': chart_data_json, 
        'resultados_presupuesto': presupuestos_activos,
    }
    
    return render(request, 'mi_finanzas/resumen_financiero.html', contexto)


# =========================================================
# 2. VISTAS DE TRANSACCIONES Y MOVIMIENTOS
# =========================================================

@login_required
def transferir_monto(request):
    """Define la lógica para la transferencia de montos (con atomicidad)."""
    
    if request.method == 'POST':
        form = TransferenciaForm(request.POST, user=request.user) 
        
        if form.is_valid():
            monto = form.cleaned_data['monto']
            cuenta_origen = form.cleaned_data['cuenta_origen']
            cuenta_destino = form.cleaned_data['cuenta_destino']

            if cuenta_origen.pk == cuenta_destino.pk:
                messages.error(request, "No puedes transferir fondos a la misma cuenta.")
                return redirect('mi_finanzas:transferir_monto')
            
            if cuenta_origen.balance < monto:
                 messages.error(request, "Saldo insuficiente en la cuenta de origen.")
                 return redirect('mi_finanzas:transferir_monto')

            try:
                # Usa atomicidad para asegurar que las dos operaciones se completen o ninguna lo haga
                with transaction.atomic():
                    # 1. ACTUALIZAR SALDOS DE CUENTAS
                    Cuenta.objects.filter(pk=cuenta_origen.pk).update(balance=F('balance') - monto)
                    Cuenta.objects.filter(pk=cuenta_destino.pk).update(balance=F('balance') + monto)
                    
                    # 2. CREAR TRANSACCIONES DE REGISTRO
                    # Nos aseguramos de que ambas transacciones se creen.
                    fecha_transaccion = timezone.localdate() 
                    
                    # Transacción de GASTO (Salida de Origen)
                    Transaccion.objects.create(
                        usuario=request.user,
                        cuenta=cuenta_origen,
                        monto=monto,
                        tipo='GASTO',
                        fecha=fecha_transaccion, 
                        descripcion=f"Transferencia Enviada a {cuenta_destino.nombre}",
                        # Garantiza que la categoría de exclusión exista
                        categoria=Categoria.objects.get_or_create(nombre='Transferencia Salida', usuario=request.user)[0] 
                    )
                    
                    # Transacción de INGRESO (Entrada a Destino)
                    Transaccion.objects.create(
                        usuario=request.user,
                        cuenta=cuenta_destino,
                        monto=monto,
                        tipo='INGRESO',
                        fecha=fecha_transaccion, 
                        descripcion=f"Transferencia Recibida de {cuenta_origen.nombre}",
                        # Garantiza que la categoría de exclusión exista
                        categoria=Categoria.objects.get_or_create(nombre='Transferencia Entrada', usuario=request.user)[0]
                    )

                messages.success(request, f"¡Transferencia de ${monto:.2f} realizada con éxito!")
                return redirect('mi_finanzas:resumen_financiero') 

            except Exception as e:
                # Si falla, se hace un rollback
                messages.error(request, f"Error al procesar la transferencia: {e}")
                
    else:
        form = TransferenciaForm(user=request.user) 
        
    context = {
        'titulo': 'Transferir Monto',
        'form': form,
    }
    
    return render(request, 'mi_finanzas/transferir_monto.html', context)


# ... (El resto de las vistas se mantienen IGUAL) ...

@login_required
def anadir_transaccion(request):
    """Añade una nueva transacción y **ACTUALIZA EL BALANCE DE LA CUENTA**."""
    
    if request.method == 'POST':
        form = TransaccionForm(request.POST, user=request.user) 
        if form.is_valid():
            
            transaccion = form.save(commit=False)
            cuenta = transaccion.cuenta
            monto = transaccion.monto
            tipo = transaccion.tipo
            
            try:
                with transaction.atomic():
                    transaccion.usuario = request.user
                    transaccion.save()
                    
                    # Aplicar el efecto al balance de la cuenta
                    if tipo == 'INGRESO':
                        Cuenta.objects.filter(pk=cuenta.pk).update(balance=F('balance') + monto)
                    else: # GASTO
                        Cuenta.objects.filter(pk=cuenta.pk).update(balance=F('balance') - monto)
                        
                    messages.success(request, "Transacción añadida y cuenta actualizada exitosamente.")
                    return redirect('mi_finanzas:resumen_financiero')

            except Exception as e:
                messages.error(request, f"Error al procesar la transacción: {e}")
                return redirect('mi_finanzas:anadir_transaccion')
    else:
        form = TransaccionForm(user=request.user)
        
    return render(request, 'mi_finanzas/anadir_transaccion.html', {'form': form})


@login_required
def editar_transaccion(request, pk):
    """
    Vista para editar una transacción existente con LÓGICA ATÓMICA.
    """
    transaccion = get_object_or_404(Transaccion, pk=pk, usuario=request.user)
    
    monto_viejo = transaccion.monto
    tipo_viejo = transaccion.tipo 
    cuenta_vieja = transaccion.cuenta

    if request.method == 'POST':
        form = TransaccionForm(request.POST, instance=transaccion, user=request.user) 
        
        if form.is_valid():
            
            with transaction.atomic():
                # --- FASE 1: REVERTIR EL EFECTO VIEJO ---
                if tipo_viejo == 'INGRESO':
                    Cuenta.objects.filter(pk=cuenta_vieja.pk).update(balance=F('balance') - monto_viejo)
                else: # GASTO
                    Cuenta.objects.filter(pk=cuenta_vieja.pk).update(balance=F('balance') + monto_viejo)
                
                # --- FASE 2: APLICAR EL NUEVO EFECTO ---
                
                nueva_transaccion = form.save(commit=False)
                nueva_transaccion.save() # Guardar los cambios de la transacción
                
                # Obtener la nueva cuenta 
                cuenta_nueva = nueva_transaccion.cuenta 
                
                # Aplicar el nuevo monto al saldo de la cuenta_nueva
                if nueva_transaccion.tipo == 'INGRESO':
                    Cuenta.objects.filter(pk=cuenta_nueva.pk).update(balance=F('balance') + nueva_transaccion.monto)
                else: # GASTO
                    Cuenta.objects.filter(pk=cuenta_nueva.pk).update(balance=F('balance') - nueva_transaccion.monto)
                
                messages.success(request, "Transacción editada y balances actualizados exitosamente.")
                return redirect('mi_finanzas:transacciones_lista')
            
    else:
        form = TransaccionForm(instance=transaccion, user=request.user) 
        
    context = {
        'form': form,
        'transaccion': transaccion,
        'titulo': f'Editar Transacción #{pk}'
    }
    return render(request, 'mi_finanzas/editar_transaccion.html', context)


@login_required
@require_POST
def eliminar_transaccion(request, pk):
    """
    Vista para eliminar una transacción y revertir su efecto en la cuenta asociada (ATÓMICO).
    """
    transaccion = get_object_or_404(Transaccion, pk=pk, usuario=request.user)
    cuenta = transaccion.cuenta
    
    try:
        # El proceso de eliminación es atómico
        with transaction.atomic():
            # 1. Revertir el efecto de la transacción antes de eliminarla
            if transaccion.tipo == 'INGRESO':
                Cuenta.objects.filter(pk=cuenta.pk).update(balance=F('balance') - transaccion.monto)
            else: # GASTO
                Cuenta.objects.filter(pk=cuenta.pk).update(balance=F('balance') + transaccion.monto)
            
            # 2. Eliminar la transacción
            transaccion.delete()

        messages.success(request, f"Transacción de '{transaccion.descripcion}' eliminada y balance revertido.")
        return redirect('mi_finanzas:transacciones_lista')

    except Exception as e:
        messages.error(request, f"Error al eliminar la transacción: {e}")
        return redirect('mi_finanzas:transacciones_lista')


@login_required
def transacciones_lista(request):
    """
    Muestra una lista de todas las transacciones del usuario.
    """
    # Consulta optimizada con select_related
    transacciones = Transaccion.objects.filter(usuario=request.user).select_related(
        'cuenta', 'categoria'
    ).order_by('-fecha')
    
    context = {
        'transacciones': transacciones,
        'titulo': 'Lista de Transacciones'
    }
    return render(request, 'mi_finanzas/transacciones_lista.html', context)


# =========================================================
# 3. VISTAS DE LISTADO Y CRUD DE CUENTAS
# =========================================================

@login_required
def cuentas_lista(request):
    """
    Muestra una lista de todas las cuentas del usuario.
    """
    cuentas = Cuenta.objects.filter(usuario=request.user).order_by('nombre')
    
    context = {
        'cuentas': cuentas,
        'titulo': 'Lista de Cuentas'
    }
    return render(request, 'mi_finanzas/cuentas_lista.html', context)


@login_required
def anadir_cuenta(request):
    """
    Vista para añadir una nueva cuenta financiera.
    """
    if request.method == 'POST':
        form = CuentaForm(request.POST) 
        if form.is_valid():
            try:
                cuenta = form.save(commit=False)
                cuenta.usuario = request.user
                cuenta.save()
                messages.success(request, "Cuenta añadida exitosamente.")
                return redirect('mi_finanzas:cuentas_lista') 
            except IntegrityError:
                messages.error(request, "Ya tienes una cuenta con ese nombre. Los nombres deben ser únicos.")
            except Exception as e:
                messages.error(request, f"Error al guardar la cuenta: {e}")

    else:
        form = CuentaForm()
        
    context = {
        'form': form,
        'titulo': 'Añadir Nueva Cuenta'
    }
    return render(request, 'mi_finanzas/anadir_cuenta.html', context)


@login_required
def editar_cuenta(request, pk):
    """
    Vista para editar una cuenta existente.
    """
    cuenta = get_object_or_404(Cuenta, pk=pk, usuario=request.user)
    
    if request.method == 'POST':
        form = CuentaForm(request.POST, instance=cuenta) 
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"Cuenta '{cuenta.nombre}' actualizada exitosamente.")
                return redirect('mi_finanzas:cuentas_lista') 
            except IntegrityError:
                messages.error(request, "Ya tienes una cuenta con ese nombre. Los nombres deben ser únicos.")
            except Exception as e:
                messages.error(request, f"Error al guardar la cuenta: {e}")

    else:
        form = CuentaForm(instance=cuenta)
        
    context = {
        'form': form,
        'titulo': f'Editar Cuenta: {cuenta.nombre}',
        'cuenta': cuenta 
    }
    return render(request, 'mi_finanzas/editar_cuenta.html', context)


@login_required
@require_POST
def eliminar_cuenta(request, pk):
    """
    Vista para eliminar una cuenta existente.
    """
    cuenta = get_object_or_404(Cuenta, pk=pk, usuario=request.user)
    
    if Transaccion.objects.filter(cuenta=cuenta).exists():
        messages.error(request, f"No se puede eliminar la cuenta '{cuenta.nombre}' porque tiene transacciones asociadas. Elimina las transacciones primero.")
        return redirect('mi_finanzas:cuentas_lista')

    cuenta.delete()
    messages.success(request, f"Cuenta '{cuenta.nombre}' eliminada exitosamente.")
    return redirect('mi_finanzas:cuentas_lista')


# =========================================================
# 4. VISTAS DE PRESUPUESTOS
# =========================================================

@login_required
def crear_presupuesto(request):
    """
    Vista para crear un nuevo presupuesto, asegurando que no haya duplicados.
    """
    if request.method == 'POST':
        form = PresupuestoForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                presupuesto = form.save(commit=False)
                presupuesto.usuario = request.user
                presupuesto.save()
                
                messages.success(request, f'Presupuesto para {presupuesto.categoria.nombre} creado exitosamente.')
                return redirect('mi_finanzas:resumen_financiero') 
            
            except IntegrityError:
                messages.error(request, 'Ya existe un presupuesto para esta categoría en el mes y año seleccionados. Por favor, edítalo en su lugar.')
            
            except Exception as e:
                messages.error(request, f'Error al guardar el presupuesto: {e}')
                
    else:
        initial_data = {
            'mes': timezone.localdate().month,
            'anio': timezone.localdate().year,
        }
        form = PresupuestoForm(initial=initial_data, user=request.user) 
        
    context = {
        'form': form,
        'titulo': 'Crear Nuevo Presupuesto'
    }
    return render(request, 'mi_finanzas/crear_presupuesto.html', context)


@login_required
def editar_presupuesto(request, pk):
    """
    Vista para editar un presupuesto existente.
    """
    presupuesto = get_object_or_404(Presupuesto, pk=pk, usuario=request.user)
    
    if request.method == 'POST':
        # Nota: Si usas una clase basada en vista (PresupuestoUpdateView) podrías quitar esta función
        form = PresupuestoForm(request.POST, user=request.user, instance=presupuesto)
        
        if form.is_valid():
            try:
                form.save() 
                
                messages.success(request, f"Presupuesto para '{presupuesto.categoria.nombre}' actualizado exitosamente.")
                # Redireccionamos a la lista de presupuestos (debes tener la URL configurada)
                return redirect('mi_finanzas:presupuestos_lista') 
                
            except IntegrityError:
                messages.error(request, 'Ya existe un presupuesto para esta categoría en el mes y año seleccionados.')
            except Exception as e:
                messages.error(request, f"Error al guardar presupuesto: {e}")
                
    else:
        form = PresupuestoForm(user=request.user, instance=presupuesto)

    contexto = {
        'form': form,
        'presupuesto': presupuesto,
        'titulo': f'Editar Presupuesto: {presupuesto.categoria.nombre}'
    }

    return render(request, 'mi_finanzas/presupuesto_editar.html', contexto)


@login_required
@require_POST
def eliminar_presupuesto(request, pk):
    """
    Vista para eliminar un presupuesto existente.
    """
    presupuesto = get_object_or_404(Presupuesto, pk=pk, usuario=request.user)
    
    try:
        nombre_categoria = presupuesto.categoria.nombre
        presupuesto.delete()
        
        messages.success(request, f"El presupuesto para '{nombre_categoria}' ha sido eliminado.")
        return redirect('mi_finanzas:resumen_financiero')
        
    except Exception as e:
        messages.error(request, f"Error al eliminar el presupuesto: {e}")
        return redirect('mi_finanzas:resumen_financiero')


@login_required
def presupuestos_lista(request):
    """
    Muestra la lista de presupuestos creados por el usuario actual.
    """
    # 1. Obtener todos los presupuestos del usuario logueado
    presupuestos = Presupuesto.objects.filter(usuario=request.user).order_by('-anio', '-mes').select_related('categoria')
    
    # 2. Preparar el contexto
    contexto = {
        'presupuestos': presupuestos,
        'titulo': 'Lista de Presupuestos'
    }
    
    # 3. Renderizar la plantilla
    return render(request, 'mi_finanzas/presupuestos_lista.html', contexto)


# =========================================================
# 5. VISTAS DE REPORTES
# =========================================================

@login_required
def reportes_financieros(request):
    """
    Vista para generar y mostrar reportes detallados y gráficos.
    """
    usuario = request.user
    hoy = timezone.localdate()
    mes_actual = hoy.month
    anio_actual = hoy.year
    
    # Para los reportes, usamos el mismo principio de exclusión de transferencias
    cats_a_excluir = []
    try:
        cat_salida = Categoria.objects.get(nombre='Transferencia Salida', usuario=usuario)
        cat_entrada = Categoria.objects.get(nombre='Transferencia Entrada', usuario=usuario)
        cats_a_excluir = [cat_salida.pk, cat_entrada.pk]
    except Categoria.DoesNotExist:
        pass
        
    # 1. GASTOS TOTALES POR CATEGORÍA (Para Gráfico Circular)
    gastos_totales_por_categoria = Transaccion.objects.filter(
        usuario=usuario,
        tipo='GASTO',
        fecha__year=anio_actual,
        fecha__month=mes_actual
    ).exclude(
        categoria__pk__in=cats_a_excluir
    ).values('categoria__nombre').annotate(
        total=Coalesce(Sum('monto'), Decimal(0.00))
    ).order_by('-total')

    # 2. Resumen Mensual (Ingresos vs Gastos)
    # Excluimos las transferencias para el resumen mensual también
    transacciones_base_reporte = Transaccion.objects.filter(
        usuario=usuario,
        fecha__year=anio_actual,
        fecha__month=mes_actual
    ).exclude(
        categoria__pk__in=cats_a_excluir
    )
    
    resumen_mensual_agregado = transacciones_base_reporte.aggregate(
        total_ingresos=Coalesce(Sum('monto', filter=F('tipo') == 'INGRESO'), Decimal(0.00), output_field=DecimalField()),
        total_gastos=Coalesce(Sum('monto', filter=F('tipo') == 'GASTO'), Decimal(0.00), output_field=DecimalField())
    )
    
    ingresos = resumen_mensual_agregado['total_ingresos']
    gastos = resumen_mensual_agregado['total_gastos']
    flujo_caja_neto = ingresos - gastos

    context = {
        'titulo': f'Reportes y Análisis ({hoy.strftime("%B %Y")})',
        'gastos_por_categoria': gastos_totales_por_categoria,
        'resumen_mensual': {
            'ingresos': ingresos,
            'gastos': gastos,
            'neto': flujo_caja_neto
        }
    }
    return render(request, 'mi_finanzas/reportes_financieros.html', context)


# =========================================================
# 6. VISTAS BASADAS EN CLASE (Ejemplo de Edición de Presupuesto)
# =========================================================

from django.urls import reverse_lazy
from django.views.generic.edit import UpdateView 
from django.contrib.auth.mixins import LoginRequiredMixin 
# Asegúrate de importar el PresupuestoUpdateForm si lo vas a usar
# from .forms import PresupuestoUpdateForm 

# Nota: Dejé la PresupuestoUpdateView como ejemplo al final, aunque la vista funcional editar_presupuesto
# es la que estás usando arriba. Si usas esta, debes importar PresupuestoUpdateForm.

# class PresupuestoUpdateView(LoginRequiredMixin, UpdateView):
#     """
#     Permite al usuario editar el monto límite de su presupuesto.
#     """
#     model = Presupuesto
#     form_class = PresupuestoUpdateForm # Asegúrate de que este formulario exista
#     template_name = 'mi_finanzas/presupuesto_editar.html'
    
#     def get_success_url(self):
#         """Redirige al dashboard después de una edición exitosa."""
#         return reverse_lazy('mi_finanzas:resumen_financiero')

#     def get_queryset(self):
#         """Asegura que solo el usuario actual pueda editar sus presupuestos."""
#         return self.model.objects.filter(usuario=self.request.user)

#     def get_context_data(self, **kwargs):
#         """Añade el nombre de la categoría al contexto para el título de la página."""
#         context = super().get_context_data(**kwargs)
#         context['categoria_nombre'] = self.object.categoria.nombre
#         return context
