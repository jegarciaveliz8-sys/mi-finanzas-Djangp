from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
from mi_finanzas.models import Cuenta, Transaccion 


class PanelDeControlTest(TestCase):
    """Pruebas para verificar los cálculos del Panel de Control."""

    def setUp(self):
        # 1. Crear usuario de prueba
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.login(username='testuser', password='testpassword')
        
        # 2. Definir fecha de prueba 
        self.hoy = timezone.localdate()
        self.fecha_mes_anterior = self.hoy - timedelta(days=30) 
        
        # 3. Crear Cuentas de Prueba
        # Balance total que debería ser 6200.00
        self.cuenta1 = Cuenta.objects.create(usuario=self.user, nombre='Cuenta Principal', tipo='AHORROS', balance=5000.00)
        self.cuenta2 = Cuenta.objects.create(usuario=self.user, nombre='Tarjeta Crédito', tipo='TARJETA', balance=1000.00)
        self.cuenta3 = Cuenta.objects.create(usuario=self.user, nombre='Inversión', tipo='INVERSION', balance=200.00)

        # 4. Crear Transacciones de Prueba
        
        # Transacciones de este mes (Octubre)
        # Ingreso del mes: 200.00
        Transaccion.objects.create(usuario=self.user, cuenta=self.cuenta1, monto=200.00, tipo='INGRESO', fecha=self.hoy)
        
        # Gasto del mes: 500.00
        Transaccion.objects.create(usuario=self.user, cuenta=self.cuenta2, monto=500.00, tipo='GASTO', fecha=self.hoy)
        
        # Transacción del mes anterior (debe ser ignorada por el cálculo mensual)
        Transaccion.objects.create(usuario=self.user, cuenta=self.cuenta3, monto=1000.00, tipo='INGRESO', fecha=self.fecha_mes_anterior)


    def test_panel_de_control_calculates_correct_summary(self):
        """
        Verifica que el Panel de Control calcule y muestre los saldos correctos
        basados en los datos de setUp.
        """
        
        # 1. Hacer la petición a la vista
        response = self.client.get(reverse('mi_finanzas:resumen_financiero'))

        # 2. Verificar el código de respuesta (el usuario está logueado y la página carga)
        self.assertEqual(response.status_code, 200)

        # 3. Definir los valores esperados basados en setUp:
        saldo_neto_esperado = 6200.00 
        ingresos_esperados = 200.00
        gastos_esperados = 500.00

        # 4. Verificar los cálculos en el contexto de la respuesta (AssertionError)
        
        self.assertIn('saldo_neto_total', response.context, "La variable 'saldo_neto_total' no está en el contexto.")
        
        self.assertEqual(
            float(response.context['saldo_neto_total']), 
            saldo_neto_esperado, 
            msg=f"El Saldo Neto Total es incorrecto. Esperado: {saldo_neto_esperado}, Obtenido: {response.context['saldo_neto_total']}"
        )
        
        self.assertEqual(
            float(response.context['ingresos_del_mes']), 
            ingresos_esperados, 
            msg=f"Los Ingresos del Mes son incorrectos. Esperado: {ingresos_esperados}, Obtenido: {response.context['ingresos_del_mes']}"
        )
        
        self.assertEqual(
            float(response.context['gastos_del_mes']), 
            gastos_esperados, 
            msg=f"Los Gastos del Mes son incorrectos. Esperado: {gastos_esperados}, Obtenido: {response.context['gastos_del_mes']}"
        )

# mi_finanzas/tests/test_funcional.py

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from mi_finanzas.models import Cuenta, Transaccion # Asegúrate de que tus modelos estén importados

class PanelControlTest(TestCase):
    def setUp(self):
        # 1. Crear un usuario de prueba para la autenticación
        self.user = User.objects.create_user(username='testuser', password='password123')
        
        # 2. Crear una cuenta básica (necesaria para la vista resumen_financiero)
        self.cuenta = Cuenta.objects.create(
            usuario=self.user,
            nombre='Cuenta de Prueba',
            tipo='CORRIENTE',
            balance=100.00
        )
        
        # 3. Inicializar el cliente
        self.client = Client()

    def test_carga_correcta_panel_control(self):
        """
        Prueba que la página principal (Panel de Control) se carga correctamente 
        y contiene el título esperado.
        """
        # Autenticar el cliente
        self.client.login(username='testuser', password='password123')
        
        # Realizar la solicitud GET a la URL principal (resumen_financiero)
        response = self.client.get(reverse('mi_finanzas:resumen_financiero'))
        
        # 1. Comprobar que la solicitud fue exitosa (código 200)
        self.assertEqual(response.status_code, 200)
        
        # 2. Comprobar que el título de la página está presente
        # Busca el nombre de la plantilla base, si hereda correctamente
        self.assertContains(response, "MiFinanzas") 
        
        # 3. Comprobar que la sección de Gastos por Categoría existe
        self.assertContains(response, "Gastos por Categoría") 

    # Agrega más pruebas aquí (ej. test_login, test_anadir_transaccion, etc.)

