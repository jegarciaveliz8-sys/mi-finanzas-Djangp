from django.contrib import admin
# Importamos todos los modelos que se van a registrar en este archivo
from .models import Cuenta, Transaccion, Categoria, TransaccionRecurrente, Presupuesto 

# -------------------------------------------------------------------------
# 1. CLASE ADMIN PARA CUENTA
# -------------------------------------------------------------------------

class CuentaAdmin(admin.ModelAdmin):
    # CORRECCIÓN: 'balance' cambiado a 'saldo' para coincidir con models.py y evitar admin.E108
    list_display = ('nombre', 'usuario', 'tipo', 'saldo') 
    list_filter = ('usuario', 'tipo')
    search_fields = ('nombre', 'usuario__username')

# -------------------------------------------------------------------------
# 2. CLASE ADMIN PARA TRANSACCION
# -------------------------------------------------------------------------

class TransaccionAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'usuario', 'cuenta', 'tipo', 'monto')
    list_filter = ('usuario', 'tipo', 'cuenta')
    search_fields = ('usuario__username', 'cuenta__nombre')
    date_hierarchy = 'fecha'

# -------------------------------------------------------------------------
# 3. CLASE ADMIN PARA CATEGORIA
# -------------------------------------------------------------------------

class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario') 
    list_filter = ('usuario',)
    search_fields = ('nombre',)

# -------------------------------------------------------------------------
# 4. CLASE ADMIN PARA TRANSACCION RECURRENTE (usando decorador)
# -------------------------------------------------------------------------

@admin.register(TransaccionRecurrente)
class TransaccionRecurrenteAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'monto', 'frecuencia', 'proximo_pago', 'esta_activa')
    list_filter = ('frecuencia', 'esta_activa')

# -------------------------------------------------------------------------
# 5. CLASE ADMIN PARA PRESUPUESTO (usando decorador)
# -------------------------------------------------------------------------

@admin.register(Presupuesto)
class PresupuestoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'categoria', 'monto_limite', 'mes', 'anio')
    list_filter = ('mes', 'anio', 'categoria')

# -------------------------------------------------------------------------
# 6. REGISTRO DE MODELOS (usando admin.site.register)
# -------------------------------------------------------------------------

admin.site.register(Cuenta, CuentaAdmin)
admin.site.register(Transaccion, TransaccionAdmin)
admin.site.register(Categoria, CategoriaAdmin)

# Nota: TransaccionRecurrente y Presupuesto ya están registrados arriba
# con el decorador @admin.register().


