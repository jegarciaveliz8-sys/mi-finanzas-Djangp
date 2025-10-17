from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView 
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm 
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, DecimalField, Q 
from django.db.models.functions import Coalesce
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal 
import json 
import calendar 
from django.core.serializers.json import DjangoJSONEncoder 

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
    
    # Cálculo del Saldo Total Neto (Activos + Pasivos Negativos)
    saldo_total = cuentas.aggregate(total=Coalesce(Sum('saldo'), Decimal(0), output_field=DecimalField()))['total'] 
    
    # --- LÓGICA DE FECHAS Y TRANSACCIONES DEL MES ---
    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1)
    # Usa relativedelta para manejar cambios de mes/año correctamente
    primer_dia_siguiente_mes = primer_dia_mes + relativedelta(months=1) 
    
    transacciones_mes = Transaccion.objects.filter(
        usuario=request.user, 
        fecha__gte=primer_dia_mes,
        fecha__lt=primer_dia_siguiente_mes
    )
    
    # 🚀 REFINAMIENTO CRÍTICO: Usar el nuevo campo 'es_transferencia'
    transacciones_mes_sin_transfer = transacciones_mes.filter(es_transferencia=False)

    # Agregación de Ingresos y Gastos (usando el QuerySet filtrado)
    totales_mes = transacciones_mes_sin_transfer.aggregate(
        # Ingresos: Montos > 0
        ingresos=Coalesce(Sum('monto', filter=Q(monto__gt=0)), Decimal(0), output_field=DecimalField()),
        # Gastos: Montos < 0 (la suma será negativa)
        gastos=Coalesce(Sum('monto', filter=Q(monto__lt=0)), Decimal(0), output_field=DecimalField())
    )
    # ----------------------------------------------------
    
    # --- 1. LÓGICA PARA ÚLTIMAS TRANSACCIONES ---
    ultimas_transacciones = Transaccion.objects.filter(usuario=request.user).order_by('-fecha')[:5]

    # --- 2. LÓGICA PARA GRÁFICO (Gastos por Categoría) ---
    # Usamos transacciones_mes_sin_transfer
    gastos_por_categoria = transacciones_mes_sin_transfer.filter(monto__lt=0, categoria__isnull=False).values(
        'categoria__nombre'
    ).annotate(
        # Multiplicar por -1 para obtener el valor positivo del gasto
        gasto=Coalesce(Sum('monto'), Decimal(0), output_field=DecimalField()) * -1
    ).order_by('-gasto')

    chart_data = {
        'labels': [item['categoria__nombre'] for item in gastos_por_categoria],
        'data': [float(item['gasto']) for item in gastos_por_categoria], # Convertir Decimal a float para JSON
    }
    
    # Convertir a JSON seguro para pasar a la plantilla
    chart_data_json = json.dumps(chart_data)

    # --- 3. LÓGICA DE PRESUPUESTOS ---
    presupuestos_activos_list = Presupuesto.objects.filter(
        usuario=request.user, 
        # Filtro por mes/año del presupuesto
        mes=hoy.month,
        anio=hoy.year
    )
    
    resultados_presupuesto = []
    for presupuesto in presupuestos_activos_list:
        # 🚀 REFINAMIENTO CRÍTICO: Usar el nuevo campo 'es_transferencia' en el filtro de gasto
        gasto_actual_q = Transaccion.objects.filter(
            usuario=request.user,
            categoria=presupuesto.categoria,
            fecha__gte=primer_dia_mes, 
            fecha__lt=primer_dia_siguiente_mes,
            monto__lt=0,
            es_transferencia=False # <-- ¡FILTRO ACTUALIZADO!
        ).aggregate(
            total_gastado=Coalesce(Sum('monto'), Decimal(0), output_field=DecimalField())
        )['total_gastado']
        # ----------------------------------------------------
        
        gasto_actual = abs(gasto_actual_q)
        restante = presupuesto.monto_limite - gasto_actual
        porcentaje = (gasto_actual / presupuesto.monto_limite) * 100 if presupuesto.monto_limite > 0 else 0
        
        # Lógica simple de color de barra
        color_barra = 'bg-success'
        if porcentaje > 75:
            color_barra = 'bg-warning'
        if porcentaje > 100:
            color_barra = 'bg-danger'

        resultados_presupuesto.append({
            'pk': presupuesto.pk,
            'categoria': presupuesto.categoria,
            'monto_limite': presupuesto.monto_limite,
            'gasto_actual': gasto_actual,
            'restante': restante,
            'porcentaje': min(porcentaje, 100), # Limita el % de la barra visualmente a 100
            'color_barra': color_barra,
        })
    # -----------------------------------------------

    context = {
        'cuentas': cuentas,
        'saldo_total': saldo_total,
        
        # Datos del mes
        'ingresos_mes': totales_mes['ingresos'],
        # Usamos abs() para mostrar los gastos como un valor positivo, como es común en UI
        'gastos_mes': abs(totales_mes['gastos']), 
        'mes_actual_str': hoy.strftime("%B %Y"),
        
        # Nuevos datos para el panel
        'ultimas_transacciones': ultimas_transacciones,
        'chart_data_json': chart_data_json, 
        'resultados_presupuesto': resultados_presupuesto, 
        
        # 💡 CORRECCIÓN APLICADA: Usar 'form_transferencia' para el modal del dashboard
        'form_transferencia': TransferenciaForm(user=request.user),
        
        'estado_financiero': {'tipo': 'alert-info', 'mensaje': 'Bienvenido a tu resumen financiero.', 'icono': 'fas fa-info-circle'}
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
        return Transaccion.objects.filter(usuario=self.request.user).order_by('-fecha')

# ========================================================
# VISTA DE TRANSFERENCIA (Lógica de Negocio)
# ========================================================

@login_required
@transaction.atomic
def transferir_monto(request):
    """Maneja la lógica para transferir fondos entre cuentas."""
    if request.method == 'POST':
        form = TransferenciaForm(request.POST, user=request.user)
        
        if form.is_valid():
            # 1. Obtener datos limpios
            cuenta_origen = form.cleaned_data['cuenta_origen']
            cuenta_destino = form.cleaned_data['cuenta_destino']
            monto = form.cleaned_data['monto']
            fecha = form.cleaned_data['fecha']
            descripcion = form.cleaned_data['descripcion'] or 'Transferencia interna'

            # 2. Bloqueo optimista y Verificación de Saldo
            # Se usa select_for_update para prevenir problemas de concurrencia
            cuenta_origen_bloqueada = Cuenta.objects.select_for_update().get(pk=cuenta_origen.pk)
            cuenta_destino_bloqueada = Cuenta.objects.select_for_update().get(pk=cuenta_destino.pk)

            # Verificar si la cuenta de origen es una de aquellas que no debe tener saldo negativo
            saldo_futuro_origen = cuenta_origen_bloqueada.saldo - monto

            if saldo_futuro_origen < 0 and cuenta_origen_bloqueada.tipo not in ['TARJETA', 'PRESTAMO', 'HIPOTECA', 'AUTO']:
                messages.error(request, 'Saldo insuficiente en la cuenta de origen para realizar esta transferencia.')
                return redirect('mi_finanzas:resumen_financiero')

            # 3. Actualizar saldos (Manual para transferencias)
            cuenta_origen_bloqueada.saldo = saldo_futuro_origen
            cuenta_destino_bloqueada.saldo += monto
            
            cuenta_origen_bloqueada.save()
            cuenta_destino_bloqueada.save()

            # 4. Registrar y enlazar transacciones como transferencias
            
            # Egreso (Origen)
            tx_origen = Transaccion.objects.create(
                usuario=request.user, 
                cuenta=cuenta_origen_bloqueada, 
                tipo='EGRESO', 
                # ✅ CORRECCIÓN CRÍTICA: El monto debe ser POSITIVO/ABSOLUTO (monto)
                monto=monto, 
                descripcion=f"Transferencia Enviada a {cuenta_destino.nombre} ({descripcion})",
                fecha=fecha,
                es_transferencia=True 
            )
            # Ingreso (Destino)
            tx_destino = Transaccion.objects.create(
                usuario=request.user, 
                cuenta=cuenta_destino_bloqueada, 
                tipo='INGRESO', 
                monto=monto, # Correcto, es positivo
                descripcion=f"Transferencia Recibida de {cuenta_origen.nombre} ({descripcion})",
                fecha=fecha,
                es_transferencia=True
            )
            
            # Enlazar las transacciones (usando update para evitar llamar save() y su lógica de saldo)
            Transaccion.objects.filter(pk=tx_origen.pk).update(transaccion_relacionada=tx_destino)
            Transaccion.objects.filter(pk=tx_destino.pk).update(transaccion_relacionada=tx_origen)
            
            messages.success(request, '¡Transferencia realizada con éxito!')
            return redirect('mi_finanzas:resumen_financiero')
            
        else:
            # Mostrar errores de validación del formulario
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error en el formulario de transferencia: {error}")
            
    # Redirigir siempre si no se pudo completar el POST (para evitar re-envíos)
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
            messages.error(request, "Error al guardar la cuenta. Revisa los campos.")
    else:
        form = CuentaForm()

    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'form': transferencia_form,  # Formulario de transferencia para modal
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
            messages.error(request, "Error al actualizar la cuenta. Revisa los campos.")
    else:
        form = CuentaForm(instance=cuenta)

    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'form': transferencia_form,  # Clave de Transferencia
        'cuenta_form': form,         # Clave para el formulario principal de Edición/Creación.
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
@transaction.atomic
def anadir_transaccion(request):
    """Vista para añadir una nueva transacción."""
    if request.method == 'POST':
        form = TransaccionForm(request.POST, user=request.user) 
        if form.is_valid():
            transaccion = form.save(commit=False)
            transaccion.usuario = request.user
            
            # 💡 NOTA: El modelo Transaccion.save() espera un 'monto' POSITIVO 
            # y usa el 'tipo' para decidir si sumar o restar.
            # Aquí se asegura que el valor sea positivo antes de guardar:
            transaccion.monto = abs(transaccion.monto) 
            
            # 🔔 El método save() del modelo Transaccion maneja la actualización del saldo.
            transaccion.save() 
            messages.success(request, "¡Transacción añadida con éxito!")
            return redirect('mi_finanzas:transacciones_lista')
        else:
            messages.error(request, "Error al guardar la transacción. Revisa los campos.")
    else:
        # Instancia el Formulario de Transacción vacío para el GET
        form = TransaccionForm(user=request.user)

    # Prepara el formulario de Transferencia para un modal
    transferencia_form = TransferenciaForm(user=request.user)
    
    context = {
        'form': form, # Formulario principal de Transacción
        'form_transferencia': transferencia_form, # Formulario de Transferencia para el modal
        'titulo': "Añadir Nueva Transacción",
    }
    return render(request, 'mi_finanzas/anadir_transaccion.html', context)


@login_required
@transaction.atomic
def editar_transaccion(request, pk):
    """Vista para editar una transacción existente."""
    transaccion_antigua = get_object_or_404(Transaccion, pk=pk, usuario=request.user)
    
    # Si la transacción es una transferencia, no permitir la edición directa
    if transaccion_antigua.es_transferencia:
        messages.error(request, "Las transacciones de transferencia no pueden editarse directamente. Elimina y vuelve a crear la transferencia completa.")
        return redirect('mi_finanzas:transacciones_lista')

    if request.method == 'POST':
        # Usamos el argumento user para filtrar cuentas en el formulario
        form = TransaccionForm(request.POST, instance=transaccion_antigua, user=request.user) 
        
        if form.is_valid():
            transaccion_nueva = form.save(commit=False)
            
            # 💡 NOTA: El modelo Transaccion.save() espera un 'monto' POSITIVO.
            # Se asegura que el valor sea positivo antes de guardar:
            transaccion_nueva.monto = abs(transaccion_nueva.monto)
            
            # 🔔 El método save() del modelo Transaccion maneja la reversión del viejo saldo 
            # y la aplicación del nuevo saldo, incluyendo el cambio de cuenta si aplica.
            transaccion_nueva.save() 
            
            messages.success(request, "¡Transacción actualizada con éxito!")
            return redirect('mi_finanzas:transacciones_lista') 
        else:
            messages.error(request, "Error al actualizar la transacción. Revisa los campos.")
    else:
        # Al instanciar el formulario, nos aseguramos de que el monto se muestre
        # como valor absoluto (positivo), ya que el formulario lo espera así.
        transaccion_antigua.monto = abs(transaccion_antigua.monto)
        
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
    """
    Vista para eliminar una transacción y revertir su efecto en el saldo de la cuenta.
    
    ✅ CORRECCIÓN CLAVE: Esta vista depende completamente del método 
    Transaccion.delete() del modelo para actualizar el saldo.
    """
    transaccion = get_object_or_404(Transaccion, pk=pk, usuario=request.user)
    
    # 🚀 REFINAMIENTO CRÍTICO: Eliminar la transferencia completa
    if transaccion.es_transferencia and transaccion.transaccion_relacionada:
        
        # Guardamos el PK de la transacción relacionada para buscarla después de la eliminación.
        transaccion_par_pk = transaccion.transaccion_relacionada.pk
        
        if request.method == 'POST':
            # 1. Elimina la transacción actual (invoca Transaccion.delete() y revierte saldo)
            transaccion.delete()
            
            # 2. Busca y elimina la transacción par (invoca su Transaccion.delete() y revierte el otro saldo)
            try:
                transaccion_par = Transaccion.objects.get(pk=transaccion_par_pk)
                transaccion_par.delete()
            except Transaccion.DoesNotExist:
                pass # El par ya fue eliminado, no pasa nada.

            messages.success(request, "¡Transferencia eliminada y saldos ajustados con éxito!")
            return redirect('mi_finanzas:transacciones_lista')

    # -----------------------------------------------------------
    # Lógica de Transacción Normal (NO transferencia)
    
    elif request.method == 'POST':
        # ✅ CORRECCIÓN CLAVE: Simplemente llamamos a .delete()
        # El método Transaccion.delete() en el modelo se encarga de la reversión atómica del saldo.
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
        # Ordenar por año y luego por mes descendente
        return Presupuesto.objects.filter(usuario=self.request.user).order_by('-anio', '-mes')
    
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
            messages.success(request, "¡Presupuesto creado con éxito!")
            return redirect('mi_finanzas:lista_presupuestos') 
        else:
            messages.error(request, "Error al crear el presupuesto. Revisa los campos.")
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
            messages.error(request, "Error al actualizar el presupuesto. Revisa los campos.")
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
        # Se usa una descripción de presupuesto más robusta
        nombre_presupuesto = f"{presupuesto.categoria.nombre} ({calendar.month_name[presupuesto.mes].capitalize()} {presupuesto.anio})"
        presupuesto.delete()
        messages.success(request, f"El presupuesto '{nombre_presupuesto}' ha sido eliminado.")
        return redirect('mi_finanzas:lista_presupuestos')
    
    return render(request, 'mi_finanzas/eliminar_presupuesto_confirm.html', {'presupuesto': presupuesto})


# ========================================================
# VISTAS DE REPORTES (UNIFICADA)
# ========================================================

@login_required
def reportes_financieros(request):
    """
    Genera reportes financieros agregando datos de ingresos y egresos
    por los últimos 6 meses completos.
    """
    
    # 1. Determinar el rango de los últimos 6 meses completos
    hoy = date.today()
    # 5 meses atrás para obtener el sexto mes
    fecha_5_meses_atras = hoy - relativedelta(months=5) 
    # 1er día del mes de inicio (e.g., 01 de Mayo)
    fecha_inicio = fecha_5_meses_atras.replace(day=1) 
    
    transacciones = Transaccion.objects.filter(
        usuario=request.user, 
        fecha__gte=fecha_inicio
    )
    
    # 🚀 REFINAMIENTO CRÍTICO: Usar el nuevo campo 'es_transferencia' en los reportes
    transacciones_sin_transfer = transacciones.filter(es_transferencia=False)
    
    # --- 2. CÁLCULO DEL RESUMEN TOTAL (Variable esperada: 'resumen_mensual') ---
    # Total de Ingresos/Egresos en el rango de 6 meses
    totales_agregados = transacciones_sin_transfer.aggregate(
        ingresos=Coalesce(Sum('monto', filter=Q(monto__gt=0)), Decimal(0), output_field=DecimalField()),
        egresos=Coalesce(Sum('monto', filter=Q(monto__lt=0)), Decimal(0), output_field=DecimalField())
    )
    
    # Prepara el diccionario 'resumen_mensual' esperado por el HTML
    resumen_mensual = {
        'ingresos': totales_agregados['ingresos'],
        # Multiplicar egresos por -1 para que aparezca POSITIVO como "Gastos"
        'gastos': totales_agregados['egresos'] * -1, 
        'neto': totales_agregados['ingresos'] + totales_agregados['egresos']
    }
    
    # --- 3. CÁLCULO DE GASTOS POR CATEGORÍA (Variable esperada: 'gastos_por_categoria') ---
    gastos_por_categoria_qs = transacciones_sin_transfer.filter(
        monto__lt=0, 
        categoria__isnull=False
    ).values(
        'categoria__nombre'
    ).annotate(
        # Usa el alias 'total' esperado por la plantilla
        total=Coalesce(Sum('monto'), Decimal(0), output_field=DecimalField()) * -1
    ).order_by('-total')
    
    # Prepara la variable JSON para el script del gráfico
    gastos_por_categoria_json = json.dumps(list(gastos_por_categoria_qs), cls=DjangoJSONEncoder)
    
    # --- 4. Preparar el contexto final ---
    context = {
        # Lo que la plantilla espera:
        'resumen_mensual': resumen_mensual, 
        'gastos_por_categoria': gastos_por_categoria_qs, # QuerySet para la tabla HTML
        'gastos_por_categoria_json': gastos_por_categoria_json, # JSON para el script JS
        
        # Datos adicionales
        'titulo': f"Reporte de Flujo de Caja por Período ({fecha_inicio.strftime('%b %Y')} a {hoy.strftime('%b %Y')})",
        'form': TransferenciaForm(user=request.user), # Para el modal
    }
    
    return render(request, 'mi_finanzas/reportes_financieros.html', context)

