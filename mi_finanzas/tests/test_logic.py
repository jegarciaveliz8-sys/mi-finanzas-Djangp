# mi_finanzas/tests/test_logic.py
from django.test import TestCase, Client, LiveServerTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date, timedelta
# from django.db import transaction # Se mantiene solo si se usa transaction.atomic en helpers

# --- IMPORTACIONES CONSOLIDADAS ---
from mi_finanzas.models import Cuenta, Transaccion, Categoria, Presupuesto 

# Importaciones necesarias para cálculos en tests
from django.db.models import Sum, Q, DecimalField 
from django.db.models.functions import Coalesce 
from django.db import transaction # Se mantiene para el helper de transferencia

User = get_user_model()

# ========================================================
# 1. PRUEBAS DE MODELOS Y LÓGICA DE NEGOCIO CRÍTICA
# ========================================================

class FinanzasLogicTestCase(TestCase):
    """Pruebas centradas en la lógica de modelos y cálculos."""
    # NO es necesario definir 'transaction = True'. TestCase aísla las transacciones por defecto.

    def setUp(self):
        # 1. Crear un usuario de prueba
        self.user = User.objects.create_user(
            username='testuser', 
            password='testpassword'
        )

        # 2. Crear cuentas (saldos iniciales)
        # NOTA: Los saldos iniciales NO deben incluir las transacciones creadas en setUp.
        self.cuenta_principal = Cuenta.objects.create(
            usuario=self.user, nombre='Principal', tipo='CHEQUES', saldo=Decimal('1000.00')
        )
        self.cuenta_ahorros = Cuenta.objects.create(
            usuario=self.user, nombre='Ahorros', tipo='AHORROS', saldo=Decimal('5000.00')
        )
        self.tarjeta_credito = Cuenta.objects.create(
            usuario=self.user, nombre='Tarjeta Visa', tipo='TARJETA', saldo=Decimal('-200.00')
        )

        # 3. Crear categorías
        self.cat_ingreso = Categoria.objects.create(
            usuario=self.user, nombre='Salario', tipo='INGRESO'
        )
        self.cat_gasto = Categoria.objects.create(
            usuario=self.user, nombre='Alimentación', tipo='EGRESO'
        )
        
        # 4. Crear transacciones iniciales (que deben actualizar el saldo automáticamente)
        Transaccion.objects.create(
            usuario=self.user, cuenta=self.cuenta_principal, monto=Decimal('2000.00'),
            tipo='INGRESO', categoria=self.cat_ingreso, fecha=date.today() - timedelta(days=1),
            descripcion='Pago de nómina inicial'
        )
        Transaccion.objects.create(
            usuario=self.user, cuenta=self.cuenta_principal, monto=Decimal('500.00'),
            tipo='EGRESO', categoria=self.cat_gasto, fecha=date.today() - timedelta(days=1),
            descripcion='Compra en supermercado inicial'
        )
        
        # 🚨 MEJORA CRÍTICA: NO forzar el saldo manual si la lógica de la app lo hace.
        # Si tu modelo/lógica actualiza el saldo de la cuenta al guardar una Transacción, 
        # debes *confiar* en esa lógica y solo refrescar la cuenta.
        # Eliminadas las líneas: self.cuenta_principal.saldo = Decimal('3500.00') y self.cuenta_principal.save()

        # 5. Refrescar los objetos desde la base de datos para obtener el saldo final (3500.00)
        self.cuenta_principal.refresh_from_db() 
        self.cuenta_ahorros.refresh_from_db() 
        self.tarjeta_credito.refresh_from_db() 

# [--- El resto de tus métodos de prueba (test_saldo_total_neto, etc.) se mantienen ---]

# --------------------------------------------------------
# C. PRUEBAS DE INTEGRACIÓN DE VISTAS
# --------------------------------------------------------

class VistasIntegracionTestCase(LiveServerTestCase):
    """Pruebas funcionales de las vistas críticas."""
    # NO es necesario definir 'transaction = True'. LiveServerTestCase aísla las transacciones por defecto.

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='viewuser', password='viewpassword'
        )
        self.client.login(username='viewuser', password='viewpassword')
        
        # Cuentas necesarias 
        self.cuenta1 = Cuenta.objects.create(usuario=self.user, nombre='Caja', tipo='EFECTIVO', saldo=Decimal('500.00'))
        self.cuenta2 = Cuenta.objects.create(usuario=self.user, nombre='Banco', tipo='CHEQUES', saldo=Decimal('1000.00'))
        self.cat_gasto = Categoria.objects.create(usuario=self.user, nombre='Servicios', tipo='EGRESO')
        
        self.url_resumen = reverse('mi_finanzas:resumen_financiero')
        self.url_transferencia = reverse('mi_finanzas:transferir_monto')
        self.url_anadir_transaccion = reverse('mi_finanzas:anadir_transaccion')
        
        # Crear una transacción inicial (que ajusta el saldo)
        tx_inicial = Transaccion.objects.create(
            usuario=self.user, cuenta=self.cuenta2, monto=Decimal('50.00'), tipo='EGRESO',
            categoria=self.cat_gasto, fecha=date.today(), descripcion='Transaccion de prueba para eliminar'
        )
        
        # 🚨 MEJORA CRÍTICA: Eliminar la línea de saldo manual:
        # self.cuenta2.saldo = Decimal('950.00') 
        # self.cuenta2.save()
        
        self.cuenta1.refresh_from_db() 
        self.cuenta2.refresh_from_db() # El saldo correcto de Cta2 debe ser 950.00 si la lógica funciona.

        # Usar la PK de la transacción creada.
        self.tx_simple_crud = Transaccion.objects.get(pk=tx_inicial.pk)
        self.url_eliminar_transaccion = reverse('mi_finanzas:eliminar_transaccion', args=[self.tx_simple_crud.pk])

# [--- El resto de tus métodos de prueba (test_resumen_financiero_render, etc.) se mantienen ---]

