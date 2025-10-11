from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, DecimalField
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy 
from django.views.generic import CreateView 
from django.contrib.auth.models import User 
from django.views.decorators.http import require_POST 
from django.db import transaction # Importación esencial para transacciones atómicas
from django.utils import timezone  # Importación para manejar fechas y tiempos

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
    hoy = datetime.date.today()
    mes_actual = hoy.month
    anio_actual = hoy.year
    
    # 💡 OPTIMIZACIÓN 1: QuerySet Base para el mes actual
    # Esto evita repetir filtros de usuario, mes y año en cada consulta (Elimina consultas repetidas)
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
    gastos_por_categoria = transacciones_mes_base.filter(
        tipo='GASTO',
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

    # --- LÓGICA DE PRESUPUESTOS (N+1 Resuelto) ---
    # 💡 OPTIMIZACIÓN 2: Usamos select_related('categoria') para cargar la categoría
    presupuestos = Presupuesto.objects.filter(
        usuario=usuario, 
        mes=mes_actual, 
        anio=anio_actual
    ).select_related('categoria') # ⬅️ CLAVE: Elimina consultas por cada presupuesto
    
    resultados_presupuesto = []
    
    for presupuesto in presupuestos:
        # Filtramos los gastos del mes por la categoría
        gasto_real = transacciones_mes_base.filter(
            tipo='GASTO',
            categoria=presupuesto.categoria,
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

    # --- ACTIVIDAD RECIENTE (N+1 Resuelto) ---
    # 💡 OPTIMIZACIÓN 3: select_related para cargar cuenta y categoría al instante
    ultimas_transacciones = Transaccion.objects.filter(usuario=usuario).select_related(
        'cuenta', 'categoria'
    ).order_by('-fecha')[:5] # ⬅️ CLAVE: Elimina consultas por cada transacción
    
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
    """Añade una nueva transacción y **ACTUALIZA EL BALANCE DE LA CUENTA**."""
    if request.method == 'POST':
        form = TransaccionForm(request.POST, user=request.user) 
        if form.is_valid():
            
            # 1. Obtener los datos necesarios antes de guardar
            transaccion = form.save(commit=False)
            cuenta = transaccion.cuenta
            monto = transaccion.monto
            tipo = transaccion.tipo
            
            try:
                with transaction.atomic():
                    # 2. Asignar el usuario y el campo 'idao'
                    transaccion.usuario = request.user
                    # 💡 CORRECCIÓN (Mantenida): Asignar 'idao' si es necesario por el modelo
                    transaccion.idao = request.user 
                    
                    transaccion.save()
                    
                    # 3. Aplicar el efecto al balance de la cuenta (LÓGICA CRÍTICA)
                    if tipo == 'INGRESO':
                        cuenta.balance += monto
                    else: # GASTO
                        cuenta.balance -= monto
                        
                    # Guardar el nuevo balance de la cuenta
                    cuenta.save(update_fields=['balance'])
                    
                    messages.success(request, "Transacción añadida y cuenta actualizada exitosamente.")
                    return redirect('mi_finanzas:resumen_financiero')

            except Exception as e:
                messages.error(request, f"Error al procesar la transacción: {e}")
                return redirect('mi_finanzas:anadir_transaccion')
    else:
        form = TransaccionForm(user=request.user)
        
    return render(request, 'mi_finanzas/anadir_transaccion.html', {'form': form})


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction # Necesitas importar esto
from .models import Transaccion, Cuenta # Asegúrate de importar Cuenta
from .forms import TransaccionForm # Asumiendo que has creado este formulario

@login_required
def editar_transaccion(request, pk):
    """
    Vista para editar una transacción existente con LÓGICA ATÓMICA.
    Asegura que los saldos de las cuentas se actualicen correctamente.
    """
    # 1. Recuperar la transacción (Filtro de Seguridad)
    transaccion = get_object_or_404(Transaccion, pk=pk, usuario=request.user)
    
    # 2. CRÍTICO: Guardar los valores viejos ANTES de que el formulario los reemplace
    monto_viejo = transaccion.monto
    tipo_viejo = transaccion.tipo 
    cuenta_vieja = transaccion.cuenta

    if request.method == 'POST':
        form = TransaccionForm(request.POST, instance=transaccion)
        
        if form.is_valid():
            
            with transaction.atomic():
                # --- FASE 1: REVERTIR EL EFECTO VIEJO ---
                
                # Revertir el saldo de la cuenta vieja
                # Si era un Ingreso, revertimos restando. Si era Gasto, revertimos sumando.
                if tipo_viejo == 'Ingreso':
                    cuenta_vieja.saldo -= monto_viejo
                else: # Gasto
                    cuenta_vieja.saldo += monto_viejo
                cuenta_vieja.save()

                # --- FASE 2: APLICAR EL NUEVO EFECTO ---
                
                # Guardar la transacción actualizada (con commit=False)
                nueva_transaccion = form.save(commit=False)
                
                # Obtener la nueva cuenta (podría ser la misma o una nueva)
                cuenta_nueva = nueva_transaccion.cuenta 
                
                # Aplicar el nuevo monto al saldo de la cuenta_nueva
                if nueva_transaccion.tipo == 'Ingreso':
                    cuenta_nueva.saldo += nueva_transaccion.monto
                else: # Gasto
                    cuenta_nueva.saldo -= nueva_transaccion.monto
                
                # Guardar la cuenta (ya actualizada) y la transacción
                cuenta_nueva.save()
                nueva_transaccion.save()
                
            # Si todo sale bien (bloque atomic), redirigir
            return redirect('mi_finanzas:transacciones_lista')
            
    else:
        # Si es GET, inicializar el formulario con los datos existentes
        form = TransaccionForm(instance=transaccion) 
        
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
                cuenta.balance -= transaccion.monto
            else: # GASTO
                cuenta.balance += transaccion.monto
             
            # 2. Guardar el nuevo balance de la cuenta
            cuenta.save(update_fields=['balance'])
             
            # 3. Eliminar la transacción
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
    # 💡 OPTIMIZACIÓN: Añadir select_related para evitar N+1 al listar
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
            cuenta = form.save(commit=False)
            cuenta.usuario = request.user
            cuenta.save()
            messages.success(request, "Cuenta añadida exitosamente.")
            return redirect('mi_finanzas:cuentas_lista') 
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
            form.save()
            messages.success(request, f"Cuenta '{cuenta.nombre}' actualizada exitosamente.")
            return redirect('mi_finanzas:cuentas_lista') 
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
    
    # 2. Prevenir la eliminación si tiene transacciones
    if Transaccion.objects.filter(cuenta=cuenta).exists():
        messages.error(request, f"No se puede eliminar la cuenta '{cuenta.nombre}' porque tiene transacciones asociadas. Elimina las transacciones primero.")
        return redirect('mi_finanzas:cuentas_lista')

    # 3. Eliminar la cuenta
    cuenta.delete()
    messages.success(request, f"Cuenta '{cuenta.nombre}' eliminada exitosamente.")
    return redirect('mi_finanzas:cuentas_lista')


# =========================================================
# 4. VISTAS DE PRESUPUESTOS
# =========================================================

@login_required
def crear_presupuesto(request):
    """
    Vista para crear un nuevo presupuesto mensual.
    """
    if request.method == 'POST':
        form = PresupuestoForm(request.POST, user=request.user)
        if form.is_valid():
            presupuesto = form.save(commit=False)
            presupuesto.usuario = request.user
             
            # 💡 CORRECCIÓN (Mantenida): Asignar el mes y año como enteros
            now = timezone.now()
            presupuesto.mes = now.month
            presupuesto.anio = now.year
             
            presupuesto.save()
            messages.success(request, "¡Presupuesto creado exitosamente!")
            return redirect('mi_finanzas:resumen_financiero') 
    else:
        form = PresupuestoForm(user=request.user)
         
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
        form = PresupuestoForm(request.POST, user=request.user, instance=presupuesto)
         
        if form.is_valid():
            presupuesto_editado = form.save(commit=False)
            presupuesto_editado.usuario = request.user
            presupuesto_editado.save()
            messages.success(request, f"Presupuesto para '{presupuesto_editado.categoria.nombre}' actualizado exitosamente.")
            return redirect('mi_finanzas:resumen_financiero')
            
    else:
        form = PresupuestoForm(user=request.user, instance=presupuesto)
         
    context = {
        'form': form,
        'titulo': f'Editar Presupuesto: {presupuesto.categoria.nombre}'
    }
    return render(request, 'mi_finanzas/editar_presupuesto.html', context)


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


# =========================================================
# 5. VISTAS DE REPORTES
# =========================================================

@login_required
def reportes_financieros(request):
    """
    Vista para generar y mostrar reportes detallados y gráficos.
    """
    usuario = request.user
    
    # 💡 OPTIMIZACIÓN: Añadir select_related('categoria') si es necesario
    gastos_totales_por_categoria = Transaccion.objects.filter(
        usuario=usuario,
        tipo='GASTO'
    ).values('categoria__nombre').annotate(
        total=Sum('monto')
    ).order_by('-total')

    context = {
        'titulo': 'Reportes y Análisis',
        'gastos_por_categoria': gastos_totales_por_categoria,
    }
    return render(request, 'mi_finanzas/reportes_financieros.html', context)

