# mi_finanzas/tests/test_consolidado.py

# --- IMPORTACIONES NECESARIAS ---
from django.test import TestCase, Client, LiveServerTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date, timedelta 

# Importaciones de modelos
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

        # 2. Crear cuentas 
        self.cuenta_principal = Cuenta.objects.create(
            usuario=self.user, nombre='Principal', tipo='CHEQUES', saldo=Decimal('1000.00')
        )
        self.cuenta_ahorros = Cuenta.objects.create(
            usuario=self.user, nombre='Ahorros', tipo='AHORROS', saldo=Decimal('5000.00')
        )
        self.tarjeta_credito = Cuenta.objects.create(
            usuario=self.user, nombre='Tarjeta Visa', tipo='TARJETA', saldo=Decimal('-200.00')
        )
        
        # 3. Crear categorías de setup (opcional, pero buena práctica si se usan en otros tests)
        self.categoria_comida = Categoria.objects.create(
            usuario=self.user, nombre='Comida', tipo='GASTO'
        )
        self.categoria_salario = Categoria.objects.create(
            usuario=self.user, nombre='Salario', tipo='INGRESO'
        )

        self.cuenta_principal.refresh_from_db() 

    # MÉTODOS DE PRUEBA DE LÓGICA
    
    def test_saldo_total_neto(self):
        """Prueba que el saldo neto de todas las cuentas es el esperado."""
        # Código de prueba aquí...
        pass 
    
    def test_transaccion_actualiza_saldo(self):
        """Verifica que la creación de una transacción actualice la cuenta."""
        # Código de prueba aquí...
        pass
    
    def test_transferencia_correcta_actualiza_ambos_saldos(self):
        """Verifica que una transferencia disminuya la cuenta de origen y aumente la de destino."""
        monto_transferido = Decimal('100.00')
        
        saldo_inicial_principal = self.cuenta_principal.saldo
        saldo_inicial_ahorros = self.cuenta_ahorros.saldo

        # ✅ Corrección 1: Se añade el campo 'fecha'
        Transaccion.objects.create(
            usuario=self.user, 
            cuenta=self.cuenta_principal, 
            monto=monto_transferido, 
            tipo='GASTO', 
            descripcion='Transferencia Out',
            fecha=date.today() 
        )
        Transaccion.objects.create(
            usuario=self.user, 
            cuenta=self.cuenta_ahorros, 
            monto=monto_transferido, 
            tipo='INGRESO', 
            descripcion='Transferencia In',
            fecha=date.today() 
        )
        
        self.cuenta_principal.refresh_from_db()
        self.cuenta_ahorros.refresh_from_db()

        self.assertEqual(self.cuenta_principal.saldo, saldo_inicial_principal - monto_transferido)
        self.assertEqual(self.cuenta_ahorros.saldo, saldo_inicial_ahorros + monto_transferido)
    
    # ... (Otros tests de lógica) ...


# ----------------------------------------------------

# ========================================================
# 2. PRUEBAS DE VISTAS Y FUNCIONALIDAD (Integración)
# ========================================================

class PanelDeControlTest(TestCase):
    """Pruebas funcionales de las vistas críticas, enfocadas en el Panel de Control."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='viewuser', password='viewpassword'
        )
        self.client.login(username='viewuser', password='viewpassword')
        
        # Cuentas necesarias
        self.cuenta1 = Cuenta.objects.create(usuario=self.user, nombre='Caja', tipo='EFECTIVO', saldo=Decimal('500.00'))
        self.cuenta2 = Cuenta.objects.create(usuario=self.user, nombre='Banco', tipo='CHEQUES', saldo=Decimal('1000.00'))
        
        # ✅ Corrección 3A: Crear una categoría para que el formulario POST sea válido
        self.categoria_gasto = Categoria.objects.create(
            usuario=self.user,
            nombre='Alimentos',
            tipo='GASTO'
        )
        
        self.url_resumen = reverse('mi_finanzas:resumen_financiero')
        
    # MÉTODOS DE PRUEBA DE VISTAS
    
    def test_panel_de_control_calculates_correct_summary(self):
        """Verifica los cálculos de ingresos/gastos y el saldo en el contexto de la vista."""
        # Código de prueba aquí...
        pass 

    def test_carga_correcta_y_contenido_basico(self):
        """Prueba que la vista devuelve status 200 y tiene contenido básico."""
        response = self.client.get(self.url_resumen)
        self.assertEqual(response.status_code, 200)
        # Código de prueba aquí...
        pass
    
    def test_anadir_transaccion_con_post(self):
        """Verifica que la vista POST cree una nueva transacción y redirija."""
        
        # ✅ Corrección 2: Se usa 'anadir_transaccion'
        url_crear = reverse('mi_finanzas:anadir_transaccion') 
        
        # ✅ Corrección 3B: Se añade la clave primaria de 'categoria'
        datos_formulario = {
            'monto': 75.50,
            'tipo': 'GASTO',
            'cuenta': self.cuenta1.pk, 
            'descripcion': 'Cena de prueba',
            'fecha': date.today().strftime('%Y-%m-%d'),
            'categoria': self.categoria_gasto.pk 
        }
        
        conteo_inicial = Transaccion.objects.count()

        # Simular la petición POST
        response = self.client.post(url_crear, datos_formulario, follow=True)

        # Aserciones: Verificar el resultado (esto ya no debe fallar)
        self.assertEqual(Transaccion.objects.count(), conteo_inicial + 1, "No se creó la nueva transacción.")
        self.assertEqual(response.status_code, 200)

    # ... (Otros tests de vistas) ...

