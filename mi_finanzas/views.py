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
from django.db import transaction, IntegrityError # Importaciones esenciales
from django.utils import timezone 

import json
import datetime
from decimal import Decimal

# Importaciones Locales CRÍTICAS:
from .models import Cuenta, Transaccion, Categoria, Presupuesto
from .forms import (
    RegistroUsuarioForm, 
    TransaccionForm, 
    TransferenciaForm, # ¡Necesitas este formulario implementado!
    CuentaForm, 
    PresupuestoForm 
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
# 1. VISTA DE RESUMEN (PANEL DE CONTROL) - OPTIMIZADA
# =========================================================

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

    # --- CÁLCULO DE MÉTRICAS GLOBALES ---
    saldo_total_neto = Cuenta.objects.filter(usuario=usuario).aggregate(
        total=Coalesce(Sum('balance'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    # --- MÉTRICAS MENSUALES (Usando el QuerySet Base) ---
    ingresos_del_mes = transacciones_mes_base.filter(tipo='INGRESO').aggregate(
        total=Coalesce(Sum('monto'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    gastos_del_mes = transacciones_mes_base.filter(tipo='GASTO').aggregate(
        total=Coalesce(Sum('monto'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    # --- LISTA DE CUENTAS ---
    cuentas = Cuenta.objects.filter(usuario=usuario).order_by('nombre')
    
    # --- DATOS PARA GRÁFICO DE GASTOS ---
    gastos_por_categoria_qs = transacciones_mes_base.filter(
        tipo='GASTO',
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
    chart_data_json = json.dumps(chart_data)

    # --- LÓGICA DE PRESUPUESTOS (Mejorada para usar en plantilla) ---
    presupuestos_activos = Presupuesto.objects.filter(
        usuario=usuario, 
        mes=mes_actual, 
        anio=anio_actual
    ).select_related('categoria') 
    
    for presupuesto in presupuestos_activos:
        # Filtramos los gastos del mes por la categoría
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
    ultimas_transacciones = Transaccion.objects.filter(usuario=usuario).select_related(
        'cuenta', 'categoria'
    ).order_by('-fecha')[:5] 
    
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
        'saldo_total_neto': saldo_total_neto,
        'ingresos_del_mes': ingresos_del_mes,
        'gastos_del_mes': gastos_del_mes,
        'mes_actual': hoy.strftime('%B'),
        'anio_actual': anio_actual,
        'cuentas': cuentas,
        'gastos_por_categoria': gastos_por_categoria_qs,
        'chart_data': chart_data_json,
        'presupuestos': presupuestos_activos, # Variable corregida
        'ultimas_transacciones': ultimas_transacciones,
        'estado_financiero': estado_financiero,
    }
    
    return render(request, 'mi_finanzas/resumen_financiero.html', contexto)


# =========================================================
# 2. VISTAS DE TRANSACCIONES Y MOVIMIENTOS
# =========================================================

@login_required
def transferir_monto(request):
    """Define la lógica para la transferencia de montos (con atomicidad)."""
    # ... (El código de transferir_monto está bien)
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
                with transaction.atomic():
                    # 1. ACTUALIZAR SALDOS DE CUENTAS
                    Cuenta.objects.filter(pk=cuenta_origen.pk).update(balance=F('balance') - monto)
                    Cuenta.objects.filter(pk=cuenta_destino.pk).update(balance=F('balance') + monto)
                     
                    # 2. CREAR TRANSACCIONES DE REGISTRO
                    Transaccion.objects.create(
                        usuario=request.user,
                        cuenta=cuenta_origen,
                        monto=monto,
                        tipo='GASTO',
                        fecha=datetime.date.today(),
                        descripcion=f"Transferencia Enviada a {cuenta_destino.nombre}",
                        categoria=Categoria.objects.get_or_create(nombre='Transferencia Salida', usuario=request.user)[0] 
                    )
                    
                    Transaccion.objects.create(
                        usuario=request.user,
                        cuenta=cuenta_destino,
                        monto=monto,
                        tipo='INGRESO',
                        fecha=datetime.date.today(),
                        descripcion=f"Transferencia Recibida de {cuenta_origen.nombre}",
                        categoria=Categoria.objects.get_or_create(nombre='Transferencia Entrada', usuario=request.user)[0]
                    )

                messages.success(request, f"¡Transferencia de ${monto:.2f} realizada con éxito!")
                return redirect('mi_finanzas:resumen_financiero') 

            except Exception as e:
                messages.error(request, f"Error al procesar la transferencia: {e}")
                 
    else:
        form = TransferenciaForm(user=request.user) 
        
    context = {
        'titulo': 'Transferir Monto',
        'form': form,
    }
    
    return render(request, 'mi_finanzas/transferir_monto.html', context)


@login_required
def anadir_transaccion(request):
    """Añade una nueva transacción y **ACTUALIZA EL BALANCE DE LA CUENTA**."""
    # ... (El código de anadir_transaccion está bien)
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
    # ... (El código de editar_transaccion está bien)
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
    # ... (El código de eliminar_transaccion está bien)
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
    # ... (El código de transacciones_lista está bien)
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
    # ... (El código de cuentas_lista está bien)
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
    # ... (El código de anadir_cuenta está bien)
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
    # ... (El código de editar_cuenta está bien)
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
    # ... (El código de eliminar_cuenta está bien)
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
        # Nota: El formulario necesita el user para filtrar categorías/unicidad
        form = PresupuestoForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                presupuesto = form.save(commit=False)
                presupuesto.usuario = request.user
                presupuesto.save()
                 
                messages.success(request, f'Presupuesto para {presupuesto.categoria.nombre} creado exitosamente.')
                # Usar el namespace correcto
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
        # CORREGIDO: Se pasa 'user=request.user'
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
        # CORREGIDO: Se pasa 'user=request.user'
        form = PresupuestoForm(request.POST, user=request.user, instance=presupuesto)
        
        if form.is_valid():
            try:
                # El formulario maneja la unicidad en el clean()
                form.save() 
                 
                messages.success(request, f"Presupuesto para '{presupuesto.categoria.nombre}' actualizado exitosamente.")
                # Redireccionamos a la lista de presupuestos (si existe en urls.py)
                return redirect('presupuestos:lista_presupuestos') 
                 
            except IntegrityError:
                messages.error(request, 'Ya existe un presupuesto para esta categoría en el mes y año seleccionados.')
                # Si falla por unicidad, volvemos a mostrar el formulario con los errores
            except Exception as e:
                messages.error(request, f"Error al guardar presupuesto: {e}")
                
    else:
        # CORREGIDO: Se pasa 'user=request.user'
        form = PresupuestoForm(user=request.user, instance=presupuesto)

    contexto = {
        'form': form,
        'presupuesto': presupuesto,
        'titulo': f'Editar Presupuesto: {presupuesto.categoria.nombre}'
    }

    return render(request, 'presupuestos/editar_presupuesto.html', contexto)


@login_required
@require_POST
def eliminar_presupuesto(request, pk):
    """
    Vista para eliminar un presupuesto existente.
    """
    # ... (El código de eliminar_presupuesto está bien, usando redirect a resumen)
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
    return render(request, 'presupuestos/lista_presupuestos.html', contexto)


# =========================================================
# 5. VISTAS DE REPORTES
# =========================================================

@login_required
def reportes_financieros(request):
    """
    Vista para generar y mostrar reportes detallados y gráficos.
    """
    # ... (El código de reportes_financieros está bien)
    usuario = request.user
    hoy = timezone.localdate()
    mes_actual = hoy.month
    anio_actual = hoy.year
    
    # 1. GASTOS TOTALES POR CATEGORÍA (Para Gráfico Circular)
    gastos_totales_por_categoria = Transaccion.objects.filter(
        usuario=usuario,
        tipo='GASTO',
        fecha__year=anio_actual,
        fecha__month=mes_actual
    ).values('categoria__nombre').annotate(
        total=Coalesce(Sum('monto'), Decimal(0.00))
    ).order_by('-total')

    # 2. Resumen Mensual (Ingresos vs Gastos)
    resumen_mensual = Transaccion.objects.filter(
        usuario=usuario,
        fecha__year=anio_actual,
        fecha__month=mes_actual
    ).aggregate(
        total_ingresos=Coalesce(Sum('monto', filter=F('tipo') == 'INGRESO'), Decimal(0.00), output_field=DecimalField()),
        total_gastos=Coalesce(Sum('monto', filter=F('tipo') == 'GASTO'), Decimal(0.00), output_field=DecimalField())
    )
    
    ingresos = resumen_mensual['total_ingresos']
    gastos = resumen_mensual['total_gastos']
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

