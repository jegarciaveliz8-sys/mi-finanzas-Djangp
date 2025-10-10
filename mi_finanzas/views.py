from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, DecimalField, F, Case, When
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy 
from django.views.generic import CreateView 
from django.contrib.auth.models import User 
from django.views.decorators.http import require_POST 
from django.db import transaction # Importación esencial para transacciones atómicas

import json
import datetime
from decimal import Decimal

# Importaciones Locales CRÍTICAS: Aseguran que las vistas y formularios funcionen
from .models import Cuenta, Transaccion, Categoria, Presupuesto
from .forms import (
    RegistroUsuarioForm, 
    TransaccionForm, 
    TransferenciaForm,
    CuentaForm, 
    PresupuestoForm 
)


# =========================================================
# 0. VISTA DE REGISTRO DE USUARIO (La que causó el ImportError)
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
# 1. VISTA DE RESUMEN (PANEL DE CONTROL)
# =========================================================

@login_required
def resumen_financiero(request):
    usuario = request.user
    hoy = datetime.date.today()
    mes_actual = hoy.month
    anio_actual = hoy.year

    # --- CÁLCULO DE MÉTRICAS GLOBALES (Saldo Total Neto, Ingresos, Gastos) ---
    saldo_inicial_cuentas = Cuenta.objects.filter(usuario=usuario).aggregate(
        total=Coalesce(Sum('balance'), Decimal(0.00), output_field=DecimalField())
    )['total']

    transacciones_historicas_netas = Transaccion.objects.filter(
        usuario=usuario
    ).aggregate(
        neto=Coalesce(
            Sum(
                Case(
                    When(tipo='INGRESO', then=F('monto')),
                    When(tipo='GASTO', then=-F('monto')),
                    default=0,
                    output_field=DecimalField()
                )
            ),
            Decimal(0.00),
            output_field=DecimalField()
        )
    )['neto']

    saldo_total_neto = saldo_inicial_cuentas + transacciones_historicas_netas
    
    ingresos_del_mes = Transaccion.objects.filter(
        usuario=usuario, 
        tipo='INGRESO', 
        fecha__month=mes_actual, 
        fecha__year=anio_actual
    ).aggregate(
        total=Coalesce(Sum('monto'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    gastos_del_mes = Transaccion.objects.filter(
        usuario=usuario, 
        tipo='GASTO', 
        fecha__month=mes_actual, 
        fecha__year=anio_actual
    ).aggregate(
        total=Coalesce(Sum('monto'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    # --- LISTA DE CUENTAS (para mostrar en el resumen) ---
    cuentas = Cuenta.objects.filter(usuario=usuario).order_by('nombre')
    
    # --- DATOS PARA GRÁFICO DE GASTOS ---
    gastos_por_categoria = Transaccion.objects.filter(
        usuario=usuario,
        tipo='GASTO',
        fecha__month=mes_actual,
        fecha__year=anio_actual
    ).values('categoria__nombre').annotate(
        total=Coalesce(Sum('monto'), Decimal(0.00))
    ).order_by('-total')

    chart_labels = [gasto['categoria__nombre'] if gasto['categoria__nombre'] else 'Sin Categoría' 
                     for gasto in gastos_por_categoria if gasto['total'] > 0]
    chart_data_values = [float(gasto['total']) 
                         for gasto in gastos_por_categoria if gasto['total'] > 0]

    chart_data = {
        'labels': chart_labels,
        'data': chart_data_values
    }
    chart_data_json = json.dumps(chart_data)

    # --- LÓGICA DE PRESUPUESTOS ---
    presupuestos = Presupuesto.objects.filter(usuario=usuario, mes=mes_actual, anio=anio_actual)
    resultados_presupuesto = []
    
    for presupuesto in presupuestos:
        gasto_real = Transaccion.objects.filter(
            usuario=usuario,
            tipo='GASTO',
            categoria=presupuesto.categoria,
            fecha__month=mes_actual,
            fecha__year=anio_actual
        ).aggregate(
            total=Coalesce(Sum('monto'), Decimal(0.00))
        )['total']
        
        limite = presupuesto.monto_limite 
        porcentaje = (gasto_real / limite * 100) if limite > 0 else 0
        restante = limite - gasto_real
        
        if porcentaje <= 75:
            color_barra = 'bg-success'
        elif porcentaje <= 100:
            color_barra = 'bg-warning'
        else:
            color_barra = 'bg-danger'
                 
        resultados_presupuesto.append({
            'categoria_nombre': presupuesto.categoria.nombre,
            'limite': limite,
            'gastado': gasto_real,
            'restante': restante,
            'porcentaje': porcentaje,
            'color_barra': color_barra
        })

    # --- ACTIVIDAD RECIENTE ---
    ultimas_transacciones = Transaccion.objects.filter(usuario=usuario).order_by('-fecha')[:5]

    # --- LÓGICA DEL MENSAJE DE SALUD FINANCIERA ---
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
        'gastos_por_categoria': gastos_por_categoria,
        'chart_data': chart_data_json,
        'resultados_presupuesto': resultados_presupuesto,
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
    if request.method == 'POST':
        form = TransferenciaForm(request.POST) 
        
        if form.is_valid():
            monto = form.cleaned_data['monto']
            cuenta_origen = form.cleaned_data['cuenta_origen']
            cuenta_destino = form.cleaned_data['cuenta_destino']

            try:
                with transaction.atomic():
                    # Restar y guardar (update_fields garantiza atomicidad)
                    cuenta_origen.balance -= monto
                    cuenta_origen.save(update_fields=['balance']) 

                    # Sumar y guardar (update_fields garantiza atomicidad)
                    cuenta_destino.balance += monto
                    cuenta_destino.save(update_fields=['balance']) 
                 
                messages.success(request, f"¡Transferencia de ${monto:.2f} realizada con éxito!")
                return redirect('mi_finanzas:resumen_financiero') 

            except Exception as e:
                messages.error(request, f"Error al procesar la transferencia: {e}")
    else:
        form = TransferenciaForm()
        
    context = {
        'titulo': 'Transferir Monto',
        'form': form,
    }
    
    return render(request, 'mi_finanzas/transferir_monto.html', context)


@login_required
def anadir_transaccion(request):
    """Añade una nueva transacción."""
    if request.method == 'POST':
        form = TransaccionForm(request.POST, user=request.user) 
        if form.is_valid():
            transaccion = form.save(commit=False)
            transaccion.usuario = request.user
            transaccion.save()
            messages.success(request, "Transacción añadida exitosamente.")
            return redirect('mi_finanzas:resumen_financiero')
    else:
        form = TransaccionForm(user=request.user)
        
    return render(request, 'mi_finanzas/anadir_transaccion.html', {'form': form})


# =========================================================
# 3. VISTAS DE LISTADO Y CRUD DE CUENTAS (LA VISTA FALTANTE)
# =========================================================

@login_required
def cuentas_lista(request):
    """
    Muestra una lista de todas las cuentas del usuario.
    🛑 ESTA VISTA FUE AÑADIDA PARA RESOLVER EL AttributeError 🛑
    """
    # Filtra solo las cuentas del usuario que ha iniciado sesión
    cuentas = Cuenta.objects.filter(usuario=request.user).order_by('nombre')
    
    context = {
        'cuentas': cuentas,
        'titulo': 'Lista de Cuentas'
    }
    return render(request, 'mi_finanzas/cuentas_lista.html', context)


# ... (Asegúrate de que tus otras vistas como anadir_cuenta, editar_cuenta, 
# transacciones_lista, reportes_financieros, etc., estén implementadas después de aquí) ...

