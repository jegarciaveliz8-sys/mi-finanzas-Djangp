from django.test import LiveServerTestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction 

# Importa todos tus modelos
from mi_finanzas.models import Cuenta, Transaccion, Categoria, Presupuesto 

User = get_user_model()

# ========================================================
# PRUEBAS FUNCIONALES (VISTAS DE INTEGRACIÓN)
# ========================================================

class VistasFuncionalesTestCase(LiveServerTestCase):
    """Pruebas funcionales de las vistas críticas, simulan el navegador."""

    def setUp(self):
        self.client = Client()
        
        # 1. Crear usuario
        self.user = User.objects.create_user(
            username='viewuser', 
            password='viewpassword'
        )
        self.client.login(username='viewuser', password='viewpassword')
        
        # 2. Crear cuentas (CORREGIDO: 'balance' a 'saldo' y uso de Decimal)
        self.cuenta1 = Cuenta.objects.create(
            usuario=self.user, 
            nombre='Cuenta Principal', 
            tipo='AHORROS', 
            saldo=Decimal('5000.00')
        )
        self.cuenta2 = Cuenta.objects.create(
            usuario=self.user, 
            nombre='Tarjeta Crédito', 
            tipo='TARJETA', 
            saldo=Decimal('-1000.00') # Saldo negativo para Tarjeta
        )
        self.cuenta3 = Cuenta.objects.create(
            usuario=self.user, 
            nombre='Inversión', 
            tipo='INVERSION', 
            saldo=Decimal('200.00')
        )

        # 3. Crear categorías
        self.cat_gasto = Categoria.objects.create(
            usuario=self.user, 
            nombre='Alimentación', 
            tipo='EGRESO'
        )
        self.cat_ingreso = Categoria.objects.create(
            usuario=self.user, 
            nombre='Nómina', 
            tipo='INGRESO'
        )
        
        # 4. Crear URLs
        # Asume que 'mi_finanzas' es el namespace de tu app
        self.url_resumen = reverse('mi_finanzas:resumen_financiero') 
        self.url_anadir = reverse('mi_finanzas:anadir_transaccion')
        self.url_transferencia = reverse('mi_finanzas:transferir_monto')

        # Refrescar los saldos después de la configuración (si se usaron transacciones en setUp)
        self.cuenta1.refresh_from_db()
        self.cuenta2.refresh_from_db()
        self.cuenta3.refresh_from_db()
        
        # Saldo esperado después del setUp
        self.saldo_c1_inicial = self.cuenta1.saldo # 5000.00
        self.saldo_c2_inicial = self.cuenta2.saldo # -1000.00

    
    # --------------------------------------------------------
    # A. PRUEBAS BÁSICAS DE VISTAS (GET)
    # --------------------------------------------------------
    
    def test_resumen_financiero_renderiza_correctamente(self):
        """Asegura que la página principal (dashboard) se carga con éxito."""
        response = self.client.get(self.url_resumen)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cuenta Principal') # Verifica contenido
    
    # --------------------------------------------------------
    # B. PRUEBAS DE TRANSACCIONES (POST)
    # --------------------------------------------------------

    def test_anadir_transaccion_egreso_actualiza_saldo(self):
        """Asegura que añadir un egreso actualiza el saldo de la cuenta."""
        monto_egreso = Decimal('50.00')
        
        data = {
            'cuenta': self.cuenta1.pk, 
            'tipo': 'EGRESO', 
            'monto': monto_egreso, 
            'categoria': self.cat_gasto.pk, 
            'fecha': date.today()
        }
        
        # Simula el envío del formulario POST
        response = self.client.post(self.url_anadir, data, follow=True)
        self.assertEqual(response.status_code, 200) # Debe redirigir con éxito

        self.cuenta1.refresh_from_db()
        
        # Saldo esperado: 5000.00 - 50.00 = 4950.00
        saldo_esperado = self.saldo_c1_inicial - monto_egreso
        self.assertEqual(self.cuenta1.saldo, saldo_esperado)
        
    def test_anadir_transaccion_ingreso_actualiza_saldo(self):
        """Asegura que añadir un ingreso actualiza el saldo de la cuenta."""
        monto_ingreso = Decimal('150.00')
        
        data = {
            'cuenta': self.cuenta1.pk, 
            'tipo': 'INGRESO', 
            'monto': monto_ingreso, 
            'categoria': self.cat_ingreso.pk, 
            'fecha': date.today()
        }
        
        self.client.post(self.url_anadir, data, follow=True)

        self.cuenta1.refresh_from_db()
        
        # Saldo esperado: 5000.00 + 150.00 = 5150.00
        saldo_esperado = self.saldo_c1_inicial + monto_ingreso
        self.assertEqual(self.cuenta1.saldo, saldo_esperado)

    # --------------------------------------------------------
    # C. PRUEBAS DE TRANSFERENCIA (POST)
    # --------------------------------------------------------
    
    def test_transferencia_monto_suficiente_actualiza_saldos(self):
        """Asegura que una transferencia exitosa ajusta correctamente ambas cuentas."""
        monto_transfer = Decimal('300.00')
        
        data = {
            'cuenta_origen': self.cuenta1.pk,      # 5000.00
            'cuenta_destino': self.cuenta3.pk,     # 200.00
            'monto': monto_transfer, 
            'fecha': date.today()
        }
        
        response = self.client.post(self.url_transferencia, data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        self.cuenta1.refresh_from_db()
        self.cuenta3.refresh_from_db()
        
        # Cuenta 1 (Origen): 5000.00 - 300.00 = 4700.00
        self.assertEqual(self.cuenta1.saldo, self.saldo_c1_inicial - monto_transfer)
        
        # Cuenta 3 (Destino): 200.00 + 300.00 = 500.00
        self.assertEqual(self.cuenta3.saldo, Decimal('500.00')) 

        # Verificar que se crearon dos transacciones (Egreso en C1, Ingreso en C3)
        self.assertTrue(Transaccion.objects.filter(cuenta=self.cuenta1, es_transferencia=True, tipo='EGRESO').exists())
        self.assertTrue(Transaccion.objects.filter(cuenta=self.cuenta3, es_transferencia=True, tipo='INGRESO').exists())

    def test_transferencia_saldo_insuficiente_falla(self):
        """Asegura que una transferencia falle si el saldo es insuficiente."""
        monto_transfer = Decimal('6000.00') # Mayor que el saldo de cuenta1 (5000)
        
        data = {
            'cuenta_origen': self.cuenta1.pk,      
            'cuenta_destino': self.cuenta3.pk,     
            'monto': monto_transfer, 
            'fecha': date.today()
        }
        
        response = self.client.post(self.url_transferencia, data, follow=True)
        
        # La vista debe devolver un error y no redirigir
        self.assertContains(response, 'Saldo insuficiente', status_code=200) 
        
        self.cuenta1.refresh_from_db()
        self.cuenta3.refresh_from_db()
        
        # Los saldos deben permanecer sin cambios
        self.assertEqual(self.cuenta1.saldo, self.saldo_c1_inicial) 
        self.assertEqual(self.cuenta3.saldo, Decimal('200.00')) 

