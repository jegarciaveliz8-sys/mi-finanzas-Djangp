from django.urls import path
from . import views

# Define el namespace de la aplicación
app_name = 'mi_finanzas'

urlpatterns = [
    # Rutas de Vistas Principales
    path('', views.resumen_financiero, name='resumen_financiero'),
    path('resumen/', views.resumen_financiero, name='resumen_financiero'), 
    
    # 🎯 CORRECCIÓN CRÍTICA: Apuntamos a las vistas CORRECTAS
    path('cuentas/', views.cuentas_lista, name='cuentas_lista'),
    path('transacciones/', views.transacciones_lista, name='transacciones_lista'), 
    
    # CRUD de Cuentas
    path('anadir_cuenta/', views.anadir_cuenta, name='anadir_cuenta'),
    path('cuentas/<int:pk>/editar/', views.editar_cuenta, name='editar_cuenta'),       
    path('cuentas/<int:pk>/eliminar/', views.eliminar_cuenta, name='eliminar_cuenta'), 

    # CRUD de Transacciones (habilitadas solo las necesarias)
    path('anadir_transaccion/', views.anadir_transaccion, name='anadir_transaccion'),
    
    # 🎯 CORRECCIÓN ADICIONAL: Descomentamos la ruta de edición
    # La plantilla la necesita y causaba error de NoReverseMatch.
    path('transacciones/<int:pk>/editar/', views.editar_transaccion, name='editar_transaccion'),

    # CRUD de Presupuestos
    path('crear_presupuesto/', views.crear_presupuesto, name='crear_presupuesto'),
]

