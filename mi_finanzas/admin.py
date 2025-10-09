from django.contrib import admin
# Asegúrate de importar Categoria.
from .models import Cuenta, Transaccion, Categoria 

# --- 1. CLASE ADMIN PARA CUENTA ---
class CuentaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'tipo', 'balance') 
    list_filter = ('usuario', 'tipo')
    search_fields = ('nombre', 'usuario__username')

# --- 2. CLASE ADMIN PARA TRANSACCION ---
class TransaccionAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'usuario', 'cuenta', 'tipo', 'monto')
    list_filter = ('usuario', 'tipo', 'cuenta')
    search_fields = ('usuario__username', 'cuenta__nombre')
    date_hierarchy = 'fecha'

# --- 3. CLASE ADMIN PARA CATEGORIA (FINALMENTE CORREGIDA) ---
class CategoriaAdmin(admin.ModelAdmin):
    # Ya no incluimos 'tipo', solo los campos que existen en models.py: 'nombre' y 'usuario'.
    list_display = ('nombre', 'usuario') 
    list_filter = ('usuario',)
    search_fields = ('nombre',)

# --- 4. REGISTRO ÚNICO DE LOS MODELOS ---
admin.site.register(Cuenta, CuentaAdmin)
admin.site.register(Transaccion, TransaccionAdmin)
admin.site.register(Categoria, CategoriaAdmin)

from django.contrib import admin
from .models import TransaccionRecurrente # Asegúrate de importar

# ... (Registros existentes)

@admin.register(TransaccionRecurrente)
class TransaccionRecurrenteAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'monto', 'frecuencia', 'proximo_pago', 'esta_activa')
    list_filter = ('frecuencia', 'esta_activa')
from django.contrib import admin
from .models import Presupuesto # Asegúrate de importar

# ... (Registros existentes)

@admin.register(Presupuesto)
class PresupuestoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'categoria', 'monto_limite', 'mes', 'anio')
    list_filter = ('mes', 'anio', 'categoria')
