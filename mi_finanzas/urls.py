from django.urls import path
from . import views
from django.views.generic import TemplateView

# Define el namespace de la aplicación.
app_name = 'mi_finanzas' 

# LISTA ÚNICA Y COMPLETA DE URLS
urlpatterns = [
    
    # =========================================================
    # 1. Rutas de Autenticación
    # =========================================================
    path('registro/', views.RegistroUsuario.as_view(), name='registro'), 
    
    # =========================================================
    # 2. Rutas de Vistas Principales (Dashboard y Listados)
    # =========================================================
    # Nota: Se mantiene 'resumen_financiero' para ambas rutas, pero es recomendable usar un solo nombre para evitar ambigüedades.
    path('', views.resumen_financiero, name='resumen_financiero'),
    path('resumen/', views.resumen_financiero, name='resumen_financiero'), 
    
    # Vista de Cuentas (CLASE)
    path('cuentas/', views.CuentasListView.as_view(), name='cuentas_lista'),
    
    # Vista de Transacciones (CLASE)
    path('transacciones/lista/', views.TransaccionesListView.as_view(), name='transacciones_lista'), 
    
    # RUTA DEL MANUAL
    path('manual/', TemplateView.as_view(template_name='manual_html/index.html'), name='manual_page'),
    
    # =========================================================
    # 3. CRUD de Cuentas
    # =========================================================
    path('anadir_cuenta/', views.anadir_cuenta, name='anadir_cuenta'),
    path('cuentas/<int:pk>/editar/', views.editar_cuenta, name='editar_cuenta'),    
    path('cuentas/<int:pk>/eliminar/', views.eliminar_cuenta, name='eliminar_cuenta'), 

    # =========================================================
    # 4. CRUD de Transacciones y Operaciones
    # =========================================================
    path('anadir_transaccion/', views.anadir_transaccion, name='anadir_transaccion'),
    path('transacciones/<int:pk>/editar/', views.editar_transaccion, name='editar_transaccion'),
    path('transacciones/<int:pk>/eliminar/', views.eliminar_transaccion, name='eliminar_transaccion'),
    
    # RUTA DE TRANSFERENCIA (¡CORREGIDA!)
    # El 'name' ahora es 'transferencia' para que coincida con el modal de resumen_financiero.html
    path('transferir/', views.transferir_monto, name='transferencia'), 

    # =========================================================
    # 5. CRUD de Presupuestos
    # =========================================================
    path('presupuestos/', views.PresupuestosListView.as_view(), name='lista_presupuestos'), 
    path('crear_presupuesto/', views.crear_presupuesto, name='crear_presupuesto'),
    path('presupuesto/<int:pk>/eliminar/', views.eliminar_presupuesto, name='eliminar_presupuesto'),
    
    # RUTA DE EDICIÓN DEL PRESUPUESTO
    path('presupuesto/<int:pk>/editar/', views.editar_presupuesto, name='editar_presupuesto'),

    # =========================================================
    # 6. Reportes
    # =========================================================
    path('reportes/', views.reportes_financieros, name='reportes_financieros'),
]
