from django.urls import path
from . import views

# Define el namespace de la aplicación
# NOTA: Usamos 'presupuestos' porque las plantillas lo referencian así.
app_name = 'presupuestos' 

# LISTA ÚNICA DE URLS
urlpatterns = [
    
    # =========================================================
    # 1. Rutas de Autenticación (CRÍTICA)
    # =========================================================
    path('registro/', views.RegistroUsuario.as_view(), name='registro'), 
    
    # =========================================================
    # 2. Rutas de Vistas Principales (Dashboard y Listados)
    # =========================================================
    path('', views.resumen_financiero, name='resumen_financiero'),
    path('resumen/', views.resumen_financiero, name='resumen_financiero'), 
    path('cuentas/', views.cuentas_lista, name='cuentas_lista'),
    path('transacciones/lista/', views.transacciones_lista, name='transacciones_lista'), 
    
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
    
    # ✅ RUTA DE TRANSFERENCIA
    path('transferir/', views.transferir_monto, name='transferir_monto'),

    # =========================================================
    # 5. CRUD de Presupuestos
    # =========================================================
    # 💡 RUTA FALTANTE CORREGIDA: Se añade la URL para listar todos los presupuestos.
    path('presupuestos/', views.presupuestos_lista, name='lista_presupuestos'), 
    
    path('crear_presupuesto/', views.crear_presupuesto, name='crear_presupuesto'),
    path('presupuesto/<int:pk>/editar/', views.editar_presupuesto, name='editar_presupuesto'),
    path('presupuesto/<int:pk>/eliminar/', views.eliminar_presupuesto, name='eliminar_presupuesto'),

    # =========================================================
    # 6. Reportes
    # =========================================================
    path('reportes/', views.reportes_financieros, name='reportes_financieros'),
]

