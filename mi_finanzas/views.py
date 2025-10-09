from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, DecimalField
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.http import JsonResponse
import json
import datetime
from decimal import Decimal
from django.http import HttpResponse 
from .models import Cuenta, Transaccion, Categoria, Presupuesto
from .forms import CuentaForm, TransaccionForm, PresupuestoForm, RegistroUsuarioForm
from django.views.decorators.http import require_POST 
from django.urls import reverse_lazy 
from django.views.generic import CreateView 
from django.contrib.auth.models import User 

# =========================================================
# 1. VISTA DEL PANEL DE CONTROL (RESUMEN FINANCIERO)
# =========================================================

@login_required
def resumen_financiero(request):
    usuario = request.user
    hoy = datetime.date.today()
    mes_actual = hoy.month
    anio_actual = hoy.year

    # ---------------------------------------------------------
    # 1. CÁLCULO DE MÉTRICAS GLOBALES
    # ---------------------------------------------------------
    
    # 1A. Saldo Inicial Total (Punto de partida)
    saldo_inicial_cuentas = Cuenta.objects.filter(usuario=usuario).aggregate(
        total=Coalesce(Sum('balance'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    # 1B. Ingresos del Mes Actual
    ingresos_del_mes = Transaccion.objects.filter(
        usuario=usuario, 
        tipo='INGRESO', 
        fecha__month=mes_actual, 
        fecha__year=anio_actual
    ).aggregate(
        total=Coalesce(Sum('monto'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    # 1C. Gastos del Mes Actual
    gastos_del_mes = Transaccion.objects.filter(
        usuario=usuario, 
        tipo='GASTO', 
        fecha__month=mes_actual, 
        fecha__year=anio_actual
    ).aggregate(
        total=Coalesce(Sum('monto'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    # 🎯 CORRECCIÓN DEL SALDO TOTAL NETO
    # SALDO TOTAL NETO = Saldo Inicial + Ingresos del Mes - Gastos del Mes
    saldo_total_neto = saldo_inicial_cuentas + ingresos_del_mes - gastos_del_mes
    
    # ---------------------------------------------------------
    # 2. LISTA DE CUENTAS
    # ---------------------------------------------------------
    
    cuentas = Cuenta.objects.filter(usuario=usuario).order_by('nombre')
    
    # ---------------------------------------------------------
    # 3. DATOS PARA EL GRÁFICO DE GASTOS (Chart.js)
    # ---------------------------------------------------------
    
    # Agrupa los gastos del mes por categoría
    gastos_por_categoria = Transaccion.objects.filter(
        usuario=usuario,
        tipo='GASTO',
        fecha__month=mes_actual,
        fecha__year=anio_actual
    ).values('categoria__nombre').annotate(
        total=Coalesce(Sum('monto'), Decimal(0.00))
    ).order_by('-total')

    # Prepara los datos para el JSON del gráfico
    chart_labels = [gasto['categoria__nombre'] if gasto['categoria__nombre'] else 'Sin Categoría' 
                    for gasto in gastos_por_categoria if gasto['total'] > 0]
    chart_data_values = [float(gasto['total']) 
                         for gasto in gastos_por_categoria if gasto['total'] > 0]

    chart_data = {
        'labels': chart_labels,
        'data': chart_data_values
    }
    # Convertir a JSON seguro para incrustar en HTML
    chart_data_json = json.dumps(chart_data)


    # ---------------------------------------------------------
    # 4. LÓGICA DE PRESUPUESTOS
    # ---------------------------------------------------------

    presupuestos = Presupuesto.objects.filter(usuario=usuario, mes=mes_actual, anio=anio_actual)
    resultados_presupuesto = []
    
    for presupuesto in presupuestos:
        # Calcular el gasto real para esta categoría este mes
        gasto_real = Transaccion.objects.filter(
            usuario=usuario,
            tipo='GASTO',
            categoria=presupuesto.categoria,
            fecha__month=mes_actual,
            fecha__year=anio_actual
        ).aggregate(
            total=Coalesce(Sum('monto'), Decimal(0.00))
        )['total']
        
        # Usamos 'monto_limite'
        limite = presupuesto.monto_limite 
        
        # Calcular porcentaje y restante
        porcentaje = (gasto_real / limite * 100) if limite > 0 else 0
        restante = limite - gasto_real
        
        # Determinar el color de la barra de progreso
        if porcentaje <= 75:
            color_barra = 'bg-success'
        elif porcentaje <= 100:
            color_barra = 'bg-warning'
        else: # Gasto excede el 100%
            color_barra = 'bg-danger'
            
        resultados_presupuesto.append({
            'categoria_nombre': presupuesto.categoria.nombre,
            'limite': limite,
            'gastado': gasto_real,
            'restante': restante,
            'porcentaje': porcentaje,
            'color_barra': color_barra
        })


    # ---------------------------------------------------------
    # 5. ACTIVIDAD RECIENTE (Últimas 5 Transacciones)
    # ---------------------------------------------------------
    
    ultimas_transacciones = Transaccion.objects.filter(usuario=usuario).order_by('-fecha')[:5]


    # ---------------------------------------------------------
    # 6. LÓGICA DEL MENSAJE DE SALUD FINANCIERA
    # ---------------------------------------------------------

    # Usamos el Saldo Total Neto ACTUALIZADO
    if float(saldo_total_neto) > 500: 
        estado_financiero = {
            'tipo': 'alert-success',
            'icono': 'fas fa-thumbs-up',
            'mensaje': '¡Excelente! Tu salud financiera es fuerte. Sigue así.'
        }
    elif float(saldo_total_neto) >= 0:
        estado_financiero = {
            'tipo': 'alert-warning',
            'icono': 'fas fa-exclamation-triangle',
            'mensaje': 'Estás en territorio positivo, pero considera aumentar tus ahorros.'
        }
    else: # Saldo es negativo
        estado_financiero = {
            'tipo': 'alert-danger',
            'icono': 'fas fa-skull-crossbones',
            'mensaje': '¡ATENCIÓN! Tu balance neto es negativo. Revisa tus cuentas.'
        }


    # ---------------------------------------------------------
    # 7. CONTEXTO FINAL 
    # ---------------------------------------------------------
    
    contexto = {
        'saldo_total_neto': saldo_total_neto,
        'ingresos_del_mes': ingresos_del_mes,
        'gastos_del_mes': gastos_del_mes,
        'mes_actual': hoy.strftime('%B'),
        'anio_actual': anio_actual,
        'cuentas': cuentas,
        'gastos_por_categoria': gastos_por_categoria,
        'chart_data': chart_data_json,
        'resultados_presupuesto': resultados_presupuesto,
        'ultimas_transacciones': ultimas_transacciones,
        'estado_financiero': estado_financiero,
    }
    
    return render(request, 'mi_finanzas/resumen_financiero.html', contexto)


# =========================================================
# 2. VISTAS CRUD DE CUENTAS 
# =========================================================

@login_required
def cuentas_lista(request):
    """Muestra todas las cuentas del usuario."""
    cuentas = Cuenta.objects.filter(usuario=request.user)
    return render(request, 'mi_finanzas/cuentas_lista.html', {'cuentas': cuentas})

@login_required
def anadir_cuenta(request):
    """Añade una nueva cuenta."""
    if request.method == 'POST':
        form = CuentaForm(request.POST)
        if form.is_valid():
            cuenta = form.save(commit=False)
            cuenta.usuario = request.user
            cuenta.save()
            messages.success(request, "Cuenta añadida exitosamente.")
            return redirect('mi_finanzas:cuentas_lista')
    else:
        form = CuentaForm()
    return render(request, 'mi_finanzas/anadir_cuenta.html', {'form': form})

@login_required
def editar_cuenta(request, pk):
    """Edita una cuenta."""
    # Obtenemos la cuenta o devolvemos 404
    cuenta = get_object_or_404(Cuenta, pk=pk, usuario=request.user)
    
    if request.method == 'POST':
        # Lógica para manejar el formulario de edición
        form = CuentaForm(request.POST, instance=cuenta)
        if form.is_valid():
            form.save()
            messages.success(request, f"Cuenta '{cuenta.nombre}' actualizada exitosamente.")
            return redirect('mi_finanzas:cuentas_lista')
    else:
        # Lógica para mostrar el formulario pre-llenado
        form = CuentaForm(instance=cuenta)
        
    return render(request, 'mi_finanzas/editar_cuenta.html', {'form': form, 'cuenta': cuenta})


@login_required
@require_POST
def eliminar_cuenta(request, pk):
    """Elimina una cuenta específica del usuario actual."""
    try:
        cuenta = Cuenta.objects.get(pk=pk, usuario=request.user)
    except Cuenta.DoesNotExist:
        messages.error(request, "La cuenta especificada no existe o no tienes permiso para eliminarla.")
        return redirect('mi_finanzas:cuentas_lista')

    nombre_cuenta = cuenta.nombre
    cuenta.delete()
    
    messages.success(request, f'La cuenta "{nombre_cuenta}" ha sido eliminada exitosamente.')
    
    return redirect('mi_finanzas:cuentas_lista')

# =========================================================
# 3. VISTAS CRUD DE TRANSACCIONES Y PRESUPUESTOS
# =========================================================

@login_required
def transacciones_lista(request):
    """Muestra todas las transacciones del usuario, con opción de filtrado."""
    usuario = request.user
    transacciones_list = Transaccion.objects.filter(usuario=usuario).order_by('-fecha')

    # Obtener todas las categorías para el filtro de la plantilla
    todas_categorias = Categoria.objects.filter(usuario=usuario).order_by('nombre')
    
    # Lógica de Filtros (solo para pasar las variables que la plantilla espera)
    selected_categoria = request.GET.get('categoria', '0')
    selected_fecha_inicio = request.GET.get('fecha_inicio', '')
    selected_fecha_fin = request.GET.get('fecha_fin', '')
    
    # ... (Aquí iría la lógica de filtrado completa que ya te di) ...

    contexto = {
        'titulo': 'Historial de Transacciones',
        'transacciones': transacciones_list,
        'categorias': todas_categorias,
        'selected_categoria': selected_categoria,
        'selected_fecha_inicio': selected_fecha_inicio,
        'selected_fecha_fin': selected_fecha_fin,
    }

    # 🎯 ¡CRÍTICO! Usar render
    return render(request, 'mi_finanzas/transacciones_lista.html', contexto)

 

@login_required
def anadir_transaccion(request):
    """Añade una nueva transacción."""
    if request.method == 'POST':
        # ✅ CORREGIDO: Se pasa request.POST como el primer argumento y request.user como palabra clave.
        form = TransaccionForm(request.POST, user=request.user) 
        if form.is_valid():
            transaccion = form.save(commit=False)
            transaccion.usuario = request.user
            transaccion.save()
            messages.success(request, "Transacción añadida exitosamente.")
            return redirect('mi_finanzas:resumen_financiero')
    else:
        # ✅ CORREGIDO: Se pasa request.user solo como palabra clave.
        form = TransaccionForm(user=request.user)
        
    return render(request, 'mi_finanzas/anadir_transaccion.html', {'form': form})

@login_required
def crear_presupuesto(request):
    """Crea un nuevo presupuesto para el usuario."""
    hoy = datetime.date.today()
    
    # Prepara el formulario, limitando las categorías disponibles
    if request.method == 'POST':
        form = PresupuestoForm(request.POST, user=request.user) 
        if form.is_valid():
            presupuesto = form.save(commit=False)
            presupuesto.usuario = request.user
            
            # Asignar mes y año actuales si el formulario no lo hace
            presupuesto.mes = hoy.month
            presupuesto.anio = hoy.year
                
            presupuesto.save()
            messages.success(request, "Presupuesto creado exitosamente.")
            return redirect('mi_finanzas:resumen_financiero') 
    else:
        # Pasa el usuario al formulario para filtrar opciones si es necesario
        form = PresupuestoForm(user=request.user)

    return render(request, 'mi_finanzas/crear_presupuesto.html', {'form': form})

@login_required
def editar_transaccion(request, pk):
    """
    Edita una transacción existente del usuario.
    """
    # 1. Obtener la transacción o devolver 404
    # Esto asegura que el usuario solo pueda editar sus propias transacciones.
    transaccion = get_object_or_404(Transaccion, pk=pk, usuario=request.user)
    
    if request.method == 'POST':
        # 2. Procesar el formulario con los datos POST y la instancia actual
        # Se pasa 'user=request.user' para filtrar las opciones de cuenta y categoría
        form = TransaccionForm(request.POST, instance=transaccion, user=request.user)
        
        if form.is_valid():
            form.save()
            messages.success(request, "Transacción actualizada exitosamente.")
            
            # Redirigir a la lista de transacciones después de guardar
            return redirect('mi_finanzas:transacciones_lista')
    else:
        # 3. Mostrar el formulario pre-llenado
        form = TransaccionForm(instance=transaccion, user=request.user)
        
    # 4. Renderizar la plantilla con la RUTA CORREGIDA
    # La ruta correcta debe ser 'mi_finanzas/editar_transaccion.html'
    return render(request, 'mi_finanzas/editar_transaccion.html', {'form': form, 'transaccion': transaccion})


class RegistroUsuarioView(CreateView):
    model = User 
    form_class = RegistroUsuarioForm
    template_name = 'mi_finanzas/registro.html' 
    success_url = reverse_lazy('auth:login') 

