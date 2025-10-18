# mi_finanzas/tests/test_consolidado.py

# --- IMPORTACIONES NECESARIAS ---
from django.test import TestCase, Client, LiveServerTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date, timedelta

# Importaciones de modelos (CRÍTICAS para resolver NameError)
from mi_finanzas.models import Cuenta, Transaccion, Categoria, Presupuesto 

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

        # 2. Crear cuentas (CORRECCIÓN: usando 'saldo' en lugar de 'balance')
        self.cuenta_principal = Cuenta.objects.create(
            usuario=self.user, nombre='Principal', tipo='CHEQUES', saldo=Decimal('1000.00')
        )
        self.cuenta_ahorros = Cuenta.objects.create(
            usuario=self.user, nombre='Ahorros', tipo='AHORROS', saldo=Decimal('5000.00')
        )
        self.tarjeta_credito = Cuenta.objects.create(
            usuario=self.user, nombre='Tarjeta Visa', tipo='TARJETA', saldo=Decimal('-200.00')
        )

        # 3. Crear categorías y transacciones de setup...
        # ... (Asegúrate de que este setup esté completo) ...
        
        self.cuenta_principal.refresh_from_db() 

    # MÉTODOS DE PRUEBA DE LÓGICA
    def test_saldo_total_neto(self):
        """Prueba que el saldo neto de todas las cuentas es el esperado."""
        # ... Tu código de aserción (assert) aquí ...
        pass 
    
    def test_transaccion_actualiza_saldo(self):
        """Verifica que la creación de una transacción actualice la cuenta."""
        # ... Tu código de prueba aquí ...
        pass
    
    # ... (Añade todos los demás métodos test_ de lógica que tenías) ...


# ----------------------------------------------------

# ========================================================
# 2. PRUEBAS DE VISTAS Y FUNCIONALIDAD (Integración)
# ========================================================

class PanelDeControlTest(TestCase): # Usamos TestCase para la mayoría de las integraciones de vistas
    """Pruebas funcionales de las vistas críticas, enfocadas en el Panel de Control."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='viewuser', password='viewpassword'
        )
        self.client.login(username='viewuser', password='viewpassword')
        
        # Cuentas necesarias (CORRECCIÓN: usando 'saldo' en lugar de 'balance')
        self.cuenta1 = Cuenta.objects.create(usuario=self.user, nombre='Caja', tipo='EFECTIVO', saldo=Decimal('500.00'))
        self.cuenta2 = Cuenta.objects.create(usuario=self.user, nombre='Banco', tipo='CHEQUES', saldo=Decimal('1000.00'))
        
        self.url_resumen = reverse('mi_finanzas:resumen_financiero')
        
    # MÉTODOS DE PRUEBA DE VISTAS
    def test_panel_de_control_calculates_correct_summary(self):
        """Verifica los cálculos de ingresos/gastos y el saldo en el contexto de la vista."""
        # ... Tu código de aserción (assert) aquí ...
        pass 

    def test_carga_correcta_y_contenido_basico(self):
        """Prueba que la vista devuelve status 200 y tiene contenido básico."""
        response = self.client.get(self.url_resumen)
        self.assertEqual(response.status_code, 200)
        # ... Tu código de aserción de contenido aquí ...
        pass
    
    # ... (Añade todos los demás métodos test_ de vistas que tenías) ...

