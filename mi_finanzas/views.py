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
from .models import Cuenta, Transaccion, Categoria, Presupuesto
# 🎯 CORRECCIÓN: Asegurar que todos los formularios necesarios estén importados
from .forms import (
    RegistroUsuarioForm, 
    TransaccionForm, 
    TransferenciaForm, # <-- ¡CRÍTICO! Soluciona NameError
    CuentaForm, # Asumiendo que existe
    PresupuestoForm # Asumiendo que existe
    
)

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

    # ---------------------------------------------------------
    # 1. CÁLCULO DE MÉTRICAS GLOBALES
    # ---------------------------------------------------------
    
    # 1A. Suma del Balance Inicial de TODAS las cuentas 
    saldo_inicial_cuentas = Cuenta.objects.filter(usuario=usuario).aggregate(
        total=Coalesce(Sum('balance'), Decimal(0.00), output_field=DecimalField())
    )['total']

    # 1B. Cálculo de TODAS las transacciones netas históricas
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

    # 🎯 SALDO TOTAL NETO REAL Y HISTÓRICO (Cálculo Dinámico)
    saldo_total_neto = saldo_inicial_cuentas + transacciones_historicas_netas
    
    # 1C. Ingresos del Mes Actual
    ingresos_del_mes = Transaccion.objects.filter(
        usuario=usuario, 
        tipo='INGRESO', 
        fecha__month=mes_actual, 
        fecha__year=anio_actual
    ).aggregate(
        total=Coalesce(Sum('monto'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    # 1D. Gastos del Mes Actual
    gastos_del_mes = Transaccion.objects.filter(
        usuario=usuario, 
        tipo='GASTO', 
        fecha__month=mes_actual, 
        fecha__year=anio_actual
    ).aggregate(
        total=Coalesce(Sum('monto'), Decimal(0.00), output_field=DecimalField())
    )['total']
    
    # ---------------------------------------------------------
    # 2. LISTA DE CUENTAS
    # ---------------------------------------------------------
    
    cuentas = Cuenta.objects.filter(usuario=usuario).order_by('nombre')
    
    # ---------------------------------------------------------
    # 3. DATOS PARA GRÁFICO DE GASTOS
    # ---------------------------------------------------------
    
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
        
        limite = presupuesto.monto_limite 
        
        # Calcular porcentaje y restante
        porcentaje = (gasto_real / limite * 100) if limite > 0 else 0
        restante = limite - gasto_real
        
        # Determinar el color de la barra de progreso
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


    # ---------------------------------------------------------
    # 5. ACTIVIDAD RECIENTE (Últimas 5 Transacciones)
    # ---------------------------------------------------------
    
    ultimas_transacciones = Transaccion.objects.filter(usuario=usuario).order_by('-fecha')[:5]


    # ---------------------------------------------------------
    # 6. LÓGICA DEL MENSAJE DE SALUD FINANCIERA
    # ---------------------------------------------------------

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
# 2. VISTAS DE TRANSACCIONES Y MOVIMIENTOS
# =========================================================

@login_required
def transferir_monto(request):
    """Define la lógica para la transferencia de montos."""
    # 1. Manejar el Envío del Formulario (POST)
    if request.method == 'POST':
        form = TransferenciaForm(request.POST) 
        
        if form.is_valid():
            # Extraer datos validados del formulario
            monto = form.cleaned_data['monto']
            cuenta_origen = form.cleaned_data['cuenta_origen']
            cuenta_destino = form.cleaned_data['cuenta_destino']

            # La transferencia es una operación atómica: O se hacen los dos cambios, o ninguno.
            try:
                with transaction.atomic():
                    # a) Restar el monto de la cuenta de origen
                    cuenta_origen.balance -= monto
                    # 🟢 CORRECCIÓN DE INTEGRIDAD: Forzar la actualización del campo balance
                    cuenta_origen.save(update_fields=['balance']) 

                    # b) Sumar el monto a la cuenta de destino
                    cuenta_destino.balance += monto
                    # 🟢 CORRECCIÓN DE INTEGRIDAD: Forzar la actualización del campo balance
                    cuenta_destino.save(update_fields=['balance']) 

                    # Opcional: Crear un registro de actividad o Transacción aquí
                
                # Mensaje de éxito y redirección
                messages.success(request, f"¡Transferencia de ${monto:.2f} realizada con éxito!")
                # 🟢 CORRECCIÓN DE REDIRECCIÓN: Usar nombre de ruta sin punto
                return redirect('mi_finanzas:resumen_financiero') 

            except Exception as e:
                # Manejo de cualquier fallo en la base de datos
                messages.error(request, f"Error al procesar la transferencia: {e}")
    # 2. Manejar la Solicitud Inicial (GET) o Fallo en la Validación del POST
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
# ... (otras vistas: cuentas_lista, anadir_cuenta, eliminar_cuenta, transacciones_lista, etc.) ...
# Por brevedad, se omite el resto del código CRUD y reportes, asumiendo que ya funcionan.

# 💡 NOTA: Asegúrate de que todas las demás vistas (CRUD, reportes, etc.) también estén en tu archivo.
# 💡 IMPORTANTE: Si usas la convención 'mi_finanzas:nombre_ruta' en tu redirect, debes usarla consistentemente.
# He corregido la línea de redirección en transferir_monto a return redirect('mi_finanzas:resumen_financiero')

