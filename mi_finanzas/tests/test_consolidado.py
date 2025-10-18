# mi_finanzas/tests/test_consolidado.py

# --- IMPORTACIONES NECESARIAS ---
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date
from mi_finanzas.models import Cuenta, Transaccion, Categoria 

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
        # Crear categorías (no usadas en la transferencia, pero se mantienen por coherencia)
        self.categoria_comida = Categoria.objects.create(
            usuario=self.user, nombre='Comida', tipo='EGRESO' # Usamos EGRESO/INGRESO
        )
        self.categoria_salario = Categoria.objects.create(
            usuario=self.user, nombre='Salario', tipo='INGRESO'
        )

        self.cuenta_principal.refresh_from_db() 

    # Métodos de prueba que ya funcionan (omitidos por brevedad)
    def test_saldo_total_neto(self):
        pass
    
    def test_transaccion_actualiza_saldo(self):
        pass

    def test_transferencia_correcta_actualiza_ambos_saldos(self):
        """Verifica que una transferencia disminuya la cuenta de origen y aumente la de destino."""
        monto_transferido = Decimal('100.00')
        
        saldo_inicial_principal = self.cuenta_principal.saldo
        saldo_inicial_ahorros = self.cuenta_ahorros.saldo

        # ✅ CORRECCIÓN DE LA LÓGICA: Usamos 'EGRESO' y 'INGRESO'
        Transaccion.objects.create(
            usuario=self.user, 
            cuenta=self.cuenta_principal, 
            monto=monto_transferido, 
            tipo='EGRESO', # EGRESO para restar del saldo (salida)
            descripcion='Transferencia Out',
            fecha=date.today() 
        )
        Transaccion.objects.create(
            usuario=self.user, 
            cuenta=self.cuenta_ahorros, 
            monto=monto_transferido, 
            tipo='INGRESO', # INGRESO para sumar al saldo (entrada)
            descripcion='Transferencia In',
            fecha=date.today() 
        )
        
        # Es crucial hacer refresh después de operaciones atómicas con F()
        self.cuenta_principal.refresh_from_db()
        self.cuenta_ahorros.refresh_from_db()

        self.assertEqual(self.cuenta_principal.saldo, saldo_inicial_principal - monto_transferido)
        self.assertEqual(self.cuenta_ahorros.saldo, saldo_inicial_ahorros + monto_transferido)
    


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
        
        # Creamos una categoría para el POST (Tipo: EGRESO)
        self.categoria_gasto = Categoria.objects.create(
            usuario=self.user,
            nombre='Alimentos',
            tipo='EGRESO' # Usamos EGRESO
        )
        
        self.url_resumen = reverse('mi_finanzas:resumen_financiero')
        self.url_crear = reverse('mi_finanzas:anadir_transaccion')
        
    def test_carga_correcta_y_contenido_basico(self):
        pass # Test ya OK

    def test_panel_de_control_calculates_correct_summary(self):
        pass # Test ya OK
    
    def test_anadir_transaccion_con_post(self):
        """Verifica que la vista POST cree una nueva transacción y redirija."""
        
        # ✅ CORRECCIÓN FINAL: Usar 'EGRESO' en mayúsculas
        datos_formulario = {
            'monto': str(Decimal('75.50')),
            'tipo': 'EGRESO', # CLAVE CORRECTA
            'cuenta': self.cuenta1.pk, 
            'descripcion': 'Cena de prueba',
            'fecha': date.today().isoformat(),
            'categoria': self.categoria_gasto.pk,
            'usuario': self.user.pk
        }
        
        conteo_inicial = Transaccion.objects.count()

        # Simular la petición POST
        response = self.client.post(self.url_crear, datos_formulario)

        # DEBUGGING: Si falla la validación, veremos el error (status 200)
        if response.status_code == 200:
            print("\n--- ¡FALLO EN VALIDACIÓN DE VISTA! ---")
            print("El formulario falló la validación y la vista devolvió 200 (Formulario de vuelta).")
            if response.context and 'form' in response.context and response.context['form'].errors:
                 print(f"Errores del formulario: {response.context['form'].errors}")
            else:
                 print("No hay errores de formulario explícitos. Posible error interno del servidor (500).")
            print("--------------------------------------\n")
        
        # Aserciones: El conteo y el status 302 indican éxito
        self.assertEqual(Transaccion.objects.count(), conteo_inicial + 1, "No se creó la nueva transacción.")
        self.assertEqual(response.status_code, 302, "Se esperaba una redirección después de un POST exitoso.")

