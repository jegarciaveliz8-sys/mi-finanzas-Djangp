from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date
from .models import Cuenta, Transaccion, Categoria, Presupuesto
from .forms import TransaccionForm
# --- ¡NUEVAS IMPORTACIONES NECESARIAS! ---
from django.db.models import Sum, Q, DecimalField
from django.db.models.functions import Coalesce


User = get_user_model()

# ========================================================
# 1. PRUEBAS DE MODELOS Y LÓGICA DE NEGOCIO CRÍTICA
# ========================================================

class FinanzasLogicTestCase(TestCase):
    """Pruebas centradas en la lógica de modelos y cálculos."""

    def setUp(self):
        # 1. Crear un usuario de prueba
        self.user = User.objects.create_user(
            username='testuser', 
            password='testpassword'
        )

        # 2. Crear cuentas
        self.cuenta_principal = Cuenta.objects.create(
            usuario=self.user, 
            nombre='Principal', 
            tipo='CHEQUES', 
            saldo=Decimal('1000.00')
        )
        self.cuenta_ahorros = Cuenta.objects.create(
            usuario=self.user, 
            nombre='Ahorros', 
            tipo='AHORROS', 
            saldo=Decimal('5000.00')
        )
        self.tarjeta_credito = Cuenta.objects.create(
            usuario=self.user, 
            nombre='Tarjeta Visa', 
            tipo='TARJETA', 
            saldo=Decimal('-200.00')
        )

        # 3. Crear categorías
        self.cat_ingreso = Categoria.objects.create(
            usuario=self.user, 
            nombre='Salario', 
            tipo='INGRESO'
        )
        self.cat_gasto = Categoria.objects.create(
            usuario=self.user, 
            nombre='Alimentación', 
            tipo='EGRESO'
        )

        # 4. Crear transacciones iniciales (Fecha de hoy para el mes actual)
        Transaccion.objects.create(
            usuario=self.user,
            cuenta=self.cuenta_principal,
            monto=Decimal('2000.00'),
            tipo='INGRESO',
            categoria=self.cat_ingreso,
            fecha=date.today(),
            descripcion='Pago de nómina'
        )
        Transaccion.objects.create(
            usuario=self.user,
            cuenta=self.cuenta_principal,
            monto=Decimal('-500.00'),
            tipo='EGRESO',
            categoria=self.cat_gasto,
            fecha=date.today(),
            descripcion='Compra en supermercado'
        )

# --------------------------------------------------------
# A. PRUEBAS DE SALDOS Y AGREGACIÓN
# --------------------------------------------------------

    def test_saldo_total_neto(self):
        """Asegura que el Saldo Total Neto se calcula correctamente (Activos - Pasivos)."""
        # Saldo esperado: 1000 (Principal) + 5000 (Ahorros) + (-200) (Tarjeta) = 5800.00
        cuentas = Cuenta.objects.filter(usuario=self.user)
        saldo_neto = cuentas.aggregate(
            total=Coalesce(Sum('saldo'), Decimal(0), output_field=DecimalField())
        )['total']
        self.assertEqual(saldo_neto, Decimal('5800.00'))

    def test_transaccion_ajusta_saldo(self):
        """Asegura que una nueva transacción ajuste correctamente el saldo de la cuenta."""
        # Saldo inicial de Ahorros: 5000.00
        Transaccion.objects.create(
            usuario=self.user,
            cuenta=self.cuenta_ahorros,
            monto=Decimal('-100.00'),
            tipo='EGRESO',
            fecha=date.today(),
            descripcion='Retiro'
        )
        self.cuenta_ahorros.refresh_from_db()
        # Saldo esperado: 5000.00 - 100.00 = 4900.00
        self.assertEqual(self.cuenta_ahorros.saldo, Decimal('4900.00'))

# --------------------------------------------------------
# B. PRUEBAS DE TRANSFERENCIA (LÓGICA CRÍTICA DE REFINAMIENTO)
# --------------------------------------------------------

    def test_transferencia_crea_dos_transacciones_enlazadas(self):
        """Asegura que una transferencia crea dos Transacciones con es_transferencia=True y enlazadas."""
        monto_transfer = Decimal('100.00')
        
        # 1. Simular la transferencia de la función transferir_monto
        tx_origen = Transaccion.objects.create(
            usuario=self.user, 
            cuenta=self.cuenta_principal, 
            tipo='EGRESO', 
            monto=-monto_transfer,
            fecha=date.today(),
            es_transferencia=True
        )
        tx_destino = Transaccion.objects.create(
            usuario=self.user, 
            cuenta=self.cuenta_ahorros, 
            tipo='INGRESO', 
            monto=monto_transfer,
            fecha=date.today(),
            es_transferencia=True
        )
        tx_origen.transaccion_relacionada = tx_destino
        tx_destino.transaccion_relacionada = tx_origen
        tx_origen.save()
        tx_destino.save()

        # 2. Verificaciones
        self.assertTrue(tx_origen.es_transferencia)
        self.assertTrue(tx_destino.es_transferencia)
        self.assertEqual(tx_origen.transaccion_relacionada, tx_destino)
        self.assertEqual(tx_destino.transaccion_relacionada, tx_origen)

    def test_transferencia_excluida_de_flujo_caja(self):
        """Asegura que las transacciones marcadas como es_transferencia se excluyen del cálculo del dashboard."""
        
        # Crear una transferencia que no debe contarse en Ingresos/Gastos
        Transaccion.objects.create(
            usuario=self.user, 
            cuenta=self.cuenta_ahorros, 
            tipo='INGRESO', 
            monto=Decimal('500.00'),
            fecha=date.today(),
            es_transferencia=True # <-- MARCADA COMO TRANSFERENCIA
        )
        Transaccion.objects.create(
            usuario=self.user, 
            cuenta=self.cuenta_principal, 
            tipo='EGRESO', 
            monto=Decimal('-500.00'),
            fecha=date.today(),
            es_transferencia=True # <-- MARCADA COMO TRANSFERENCIA
        )
        
        # Crear un Ingreso y Gasto REALES del mes
        Transaccion.objects.create(
            usuario=self.user, 
            cuenta=self.cuenta_principal, 
            tipo='INGRESO', 
            monto=Decimal('100.00'),
            fecha=date.today(),
            es_transferencia=False
        )
        Transaccion.objects.create(
            usuario=self.user, 
            cuenta=self.cuenta_principal, 
            tipo='EGRESO', 
            monto=Decimal('-20.00'),
            fecha=date.today(),
            es_transferencia=False
        )
        
        # Obtener transacciones del mes sin transferencias (simulando resumen_financiero)
        transacciones_sin_transfer = Transaccion.objects.filter(
            usuario=self.user,
            es_transferencia=False, # <-- ¡EL FILTRO DE ROBUSTEZ!
            fecha__month=date.today().month
        )
        
        totales = transacciones_sin_transfer.aggregate(
            ingresos=Coalesce(Sum('monto', filter=Q(monto__gt=0)), Decimal(0)),
            gastos=Coalesce(Sum('monto', filter=Q(monto__lt=0)), Decimal(0))
        )
        
        # Ingresos esperados: 2000 (nómina) + 100 (real) = 2100
        self.assertEqual(totales['ingresos'], Decimal('2100.00'))
        
        # Gastos esperados: -500 (supermercado) + -20 (real) = -520.00
        self.assertEqual(totales['gastos'], Decimal('-520.00'))
        
# --------------------------------------------------------
# C. PRUEBAS DE INTEGRACIÓN DE VISTAS
# --------------------------------------------------------

class VistasIntegracionTestCase(TestCase):
    """Pruebas funcionales de las vistas críticas."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='viewuser', 
            password='viewpassword'
        )
        self.client.login(username='viewuser', password='viewpassword')
        
        # Cuentas necesarias
        self.cuenta1 = Cuenta.objects.create(
            usuario=self.user, nombre='Caja', tipo='EFECTIVO', saldo=Decimal('500.00')
        )
        self.cuenta2 = Cuenta.objects.create(
            usuario=self.user, nombre='Banco', tipo='CHEQUES', saldo=Decimal('1000.00')
        )
        self.cat_gasto = Categoria.objects.create(
            usuario=self.user, nombre='Servicios', tipo='EGRESO'
        )
        
        self.url_resumen = reverse('mi_finanzas:resumen_financiero')
        self.url_transferencia = reverse('mi_finanzas:transferir_monto')
        self.url_anadir_transaccion = reverse('mi_finanzas:anadir_transaccion')
        self.url_eliminar_transaccion = reverse('mi_finanzas:eliminar_transaccion', args=[1])


    def test_resumen_financiero_render(self):
        """Asegura que el dashboard se carga correctamente."""
        response = self.client.get(self.url_resumen)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'mi_finanzas/resumen_financiero.html')

    def test_transferencia_monto_suficiente(self):
        """Prueba una transferencia exitosa y verifica los saldos y transacciones."""
        
        data = {
            'cuenta_origen': self.cuenta2.pk, # Banco (1000.00)
            'cuenta_destino': self.cuenta1.pk, # Caja (500.00)
            'monto': Decimal('200.00'),
            'fecha': date.today(),
            'descripcion': 'Test Transfer'
        }
        
        response = self.client.post(self.url_transferencia, data, follow=True)
        
        # 1. La transferencia debe ser exitosa y redirigir
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '¡Transferencia realizada con éxito!')
        
        # 2. Verificar saldos
        self.cuenta1.refresh_from_db() # Caja debe ser 500 + 200 = 700
        self.cuenta2.refresh_from_db() # Banco debe ser 1000 - 200 = 800
        self.assertEqual(self.cuenta1.saldo, Decimal('700.00'))
        self.assertEqual(self.cuenta2.saldo, Decimal('800.00'))
        
        # 3. Verificar que se crearon 2 transacciones y están marcadas
        transacciones_transfer = Transaccion.objects.filter(es_transferencia=True).count()
        self.assertEqual(transacciones_transfer, 2)

    def test_transferencia_saldo_insuficiente(self):
        """Prueba una transferencia que falla por saldo insuficiente."""
        
        data = {
            'cuenta_origen': self.cuenta1.pk, # Caja (500.00)
            'cuenta_destino': self.cuenta2.pk,
            'monto': Decimal('600.00'),
            'fecha': date.today(),
            'descripcion': 'Transferencia fallida'
        }
        
        response = self.client.post(self.url_transferencia, data, follow=True)
        
        # 1. La transferencia debe fallar
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Saldo insuficiente en la cuenta de origen.')
        
        # 2. Verificar que los saldos NO cambiaron
        self.cuenta1.refresh_from_db()
        self.cuenta2.refresh_from_db()
        self.assertEqual(self.cuenta1.saldo, Decimal('500.00'))
        self.assertEqual(self.cuenta2.saldo, Decimal('1000.00'))

    def test_anadir_transaccion_crud_ajusta_saldo(self):
        """Prueba el ciclo CRUD de una transacción simple y la reversión de saldos."""
        
        # --- 1. CREACIÓN ---
        data_create = {
            'cuenta': self.cuenta2.pk,
            'tipo': 'EGRESO',
            'monto': Decimal('-150.00'),
            'categoria': self.cat_gasto.pk,
            'fecha': date.today(),
            'descripcion': 'Pago de luz'
        }
        
        self.client.post(self.url_anadir_transaccion, data_create, follow=True)
        self.cuenta2.refresh_from_db()
        # Saldo esperado: 1000.00 - 150.00 = 850.00
        self.assertEqual(self.cuenta2.saldo, Decimal('850.00'))
        tx_luz = Transaccion.objects.get(descripcion='Pago de luz')
        
        # --- 2. EDICIÓN ---
        url_editar = reverse('mi_finanzas:editar_transaccion', args=[tx_luz.pk])
        data_edit = data_create.copy()
        data_edit['monto'] = Decimal('-100.00') # Nuevo monto
        
        self.client.post(url_editar, data_edit, follow=True)
        self.cuenta2.refresh_from_db()
        # Lógica de edición: 850 - (-150) + (-100) = 900.00
        self.assertEqual(self.cuenta2.saldo, Decimal('900.00'))
        
        # --- 3. ELIMINACIÓN ---
        url_eliminar = reverse('mi_finanzas:eliminar_transaccion', args=[tx_luz.pk])
        self.client.post(url_eliminar, follow=True)
        self.cuenta2.refresh_from_db()
        # Lógica de eliminación: 900 - (-100) = 1000.00
        self.assertEqual(self.cuenta2.saldo, Decimal('1000.00'))
        
        # 4. Verificar que la transacción fue eliminada
        self.assertEqual(Transaccion.objects.filter(pk=tx_luz.pk).count(), 0)

