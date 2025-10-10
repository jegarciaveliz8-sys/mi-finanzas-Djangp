from django.urls import path
from . import views

# Define el namespace de la aplicación
app_name = 'mi_finanzas'

# LISTA ÚNICA DE URLS
urlpatterns = [
    
    # =========================================================
    # 1. Rutas de Autenticación (¡CRÍTICA!)
    # =========================================================
    # ✅ Añadida la ruta de registro, asumiendo que la clase en views.py se llama RegistroUsuario
    path('registro/', views.RegistroUsuario.as_view(), name='registro'), 
    # path('login/', views.LoginView.as_view(), name='login'), # (Asumiendo que usarás la vista de Django o una personalizada)
    
    # =========================================================
    # 2. Rutas de Vistas Principales (Dashboard y Listados)
    # =========================================================
    path('', views.resumen_financiero, name='resumen_financiero'),
    path('resumen/', views.resumen_financiero, name='resumen_financiero'), 
    path('cuentas/', views.cuentas_lista, name='cuentas_lista'),
    path('transacciones/', views.transacciones_lista, name='transacciones_lista'), 
    
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
    path('crear_presupuesto/', views.crear_presupuesto, name='crear_presupuesto'),
    
    # ✅ RUTA DE TRANSFERENCIA (Implementada con lógica atómica)
    path('transferir/', views.transferir_monto, name='transferir_monto'),

    # =========================================================
    # 5. Reportes
    # =========================================================
    path('reportes/', views.reportes_financieros, name='reportes_financieros'),
]

