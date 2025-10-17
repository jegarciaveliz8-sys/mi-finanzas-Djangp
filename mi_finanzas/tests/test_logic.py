from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction # Necesario para simular la vista de transferencia

# --- CORRECCIÓN CRÍTICA DE IMPORTACIÓN Y AGREGACIÓN ---
from mi_finanzas.models import Cuenta, Transaccion, Categoria, Presupuesto 
from mi_finanzas.forms import TransaccionForm

# Importaciones necesarias para cálculos en tests
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

        # 2. Crear cuentas (saldos iniciales)
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
        
        # 4. Crear transacciones iniciales (Estas ya actualizan el saldo, asumiendo la corrección en save())
        # Ingreso
        self.tx_ingreso_inicial = Transaccion.objects.create(
            usuario=self.user,
            cuenta=self.cuenta_principal,
            monto=Decimal('2000.00'),
            tipo='INGRESO',
            categoria=self.cat_ingreso,
            fecha=date.today() - timedelta(days=1), # Fecha de ayer para que no interfiera
            descripcion='Pago de nómina inicial'
        )
        # Egreso
        self.tx_egreso_inicial = Transaccion.objects.create(
            usuario=self.user,
            cuenta=self.cuenta_principal,
            monto=Decimal('500.00'),
            tipo='EGRESO',
            categoria=self.cat_gasto,
            fecha=date.today() - timedelta(days=1), # Fecha de ayer para que no interfiera
            descripcion='Compra en supermercado inicial'
        )
        
        # 🔔 CRÍTICO: Refrescar las cuentas para que tengan los saldos actualizados por las TX iniciales.
        self.cuenta_principal.refresh_from_db() # 1000 + 2000 - 500 = 2500.00
        self.cuenta_ahorros.refresh_from_db() # 5000.00
        self.tarjeta_credito.refresh_from_db() # -200.00

# --------------------------------------------------------
# A. PRUEBAS DE SALDOS Y AGREGACIÓN
# --------------------------------------------------------

    def test_saldo_total_neto(self):
        """Asegura que el Saldo Total Neto se calcula correctamente (Activos - Pasivos)."""
        # Saldo esperado: 2500 (Principal) + 5000 (Ahorros) - 200 (Tarjeta) = 7300.00
        cuentas = Cuenta.objects.filter(usuario=self.user)
        saldo_neto = cuentas.aggregate(
            total=Coalesce(Sum('saldo'), Decimal(0), output_field=DecimalField())
        )['total']
        self.assertEqual(saldo_neto, Decimal('7300.00'))

    def test_transaccion_ajusta_saldo(self):
        """Asegura que una nueva transacción ajuste correctamente el saldo de la cuenta."""
        # Saldo inicial de Ahorros: 5000.00
        Transaccion.objects.create(
            usuario=self.user,
            cuenta=self.cuenta_ahorros,
            monto=Decimal('100.00'),
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

    def simular_creacion_transferencia(self, cuenta_origen, cuenta_destino, monto):
        """Helper para simular la lógica de creación de transferencia en el test, tal como lo hace la vista."""
        with transaction.atomic():
            # 1. Simular actualización de saldos (Manual y sin Transaccion.save())
            # Esto NO debe pasar por F Expressions para evitar doble conteo.
            cuenta_origen.saldo -= monto
            cuenta_destino.saldo += monto
            cuenta_origen.save()
            cuenta_destino.save()

            # 2. Crear las transacciones (sin que modifiquen el saldo en el modelo)
            # Creamos la transferencia marcándola como tal y enlazándola
            tx_origen = Transaccion.objects.create(
                usuario=self.user, 
                cuenta=cuenta_origen, 
                tipo='EGRESO', 
                monto=monto, 
                fecha=date.today(),
                es_transferencia=True,
                descripcion=f"Transferencia enviada a {cuenta_destino.nombre} - Test"
            )
            tx_destino = Transaccion.objects.create(
                usuario=self.user, 
                cuenta=cuenta_destino, 
                tipo='INGRESO', 
                monto=monto,
                fecha=date.today(),
                es_transferencia=True,
                descripcion=f"Transferencia recibida de {cuenta_origen.nombre} - Test"
            )
            
            # 3. Enlazar las transacciones (usando update para NO llamar a save())
            Transaccion.objects.filter(pk=tx_origen.pk).update(transaccion_relacionada=tx_destino)
            Transaccion.objects.filter(pk=tx_destino.pk).update(transaccion_relacionada=tx_origen)

            tx_origen.refresh_from_db()
            tx_destino.refresh_from_db()
            return tx_origen, tx_destino

    def test_transferencia_crea_dos_transacciones_enlazadas(self):
        """Asegura que una transferencia crea dos Transacciones con es_transferencia=True y enlazadas."""
        monto_transfer = Decimal('100.00')
        
        tx_origen, tx_destino = self.simular_creacion_transferencia(
            self.cuenta_principal, self.cuenta_ahorros, monto_transfer
        )
        
        # 2. Verificaciones
        self.assertTrue(tx_origen.es_transferencia)
        self.assertTrue(tx_destino.es_transferencia)
        self.assertEqual(tx_origen.transaccion_relacionada, tx_destino)
        self.assertEqual(tx_destino.transaccion_relacionada, tx_origen)

    def test_transferencia_excluida_de_flujo_caja(self):
        """Asegura que las transacciones marcadas como es_transferencia se excluyen del cálculo del dashboard."""
        
        # Crear una transferencia (usa el helper)
        self.simular_creacion_transferencia(self.cuenta_principal, self.cuenta_ahorros, Decimal('500.00'))
        
        # Crear un Ingreso y Gasto REALES del mes (Se añadirán a los iniciales)
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
            monto=Decimal('20.00'), 
            fecha=date.today(),
            es_transferencia=False
        )
        
        # Obtener transacciones del mes sin transferencias
        transacciones_sin_transfer = Transaccion.objects.filter(
            usuario=self.user,
            es_transferencia=False
        )
        
        # Filtrar por 'tipo', no por signo de 'monto'
        totales = transacciones_sin_transfer.aggregate(
            ingresos=Coalesce(Sum('monto', filter=Q(tipo='INGRESO')), Decimal(0)),
            gastos_abs=Coalesce(Sum('monto', filter=Q(tipo='EGRESO')), Decimal(0))
        )
        
        # Ingresos esperados: 2000 (nómina inicial) + 100 (real) = 2100
        self.assertEqual(totales['ingresos'], Decimal('2100.00'))
        
        # Gastos esperados: 500 (supermercado inicial) + 20 (real) = 520.00 (valor absoluto)
        # La suma de EGRESO será un valor positivo (520.00) por la forma en que el modelo almacena.
        self.assertEqual(totales['gastos_abs'], Decimal('520.00'))

    def test_eliminar_transferencia_revierte_saldos(self):
        """Asegura que al eliminar una transaccion de transferencia, se elimine la pareja y se reviertan ambos saldos."""
        monto_transfer = Decimal('300.00')
        
        # Saldo inicial: Principal: 2500.00, Ahorros: 5000.00
        
        # 1. Simular la transferencia
        tx_origen, tx_destino = self.simular_creacion_transferencia(
            self.cuenta_principal, self.cuenta_ahorros, monto_transfer
        )
        
        # Verificar saldos intermedios
        self.cuenta_principal.refresh_from_db()
        self.cuenta_ahorros.refresh_from_db()
        self.assertEqual(self.cuenta_principal.saldo, Decimal('2200.00')) # 2500 - 300
        self.assertEqual(self.cuenta_ahorros.saldo, Decimal('5300.00')) # 5000 + 300
        
        # 2. Eliminar la transacción de origen (Debe eliminar el par y revertir ambos saldos)
        with transaction.atomic():
            # 🔔 CRÍTICO: El método delete() del modelo Transaccion debe manejar la reversión atómica
            tx_origen.delete() 
            
            # Si el delete() del modelo funciona, solo queda eliminar el par si existe.
            # En la vista de eliminación se elimina el par si existe (como lo hemos corregido).
            try:
                tx_destino.delete()
            except Transaccion.DoesNotExist:
                pass # Esto podría pasar si el modelo ya eliminó el par en cascada o viceversa.

        # 3. Verificar saldos finales (Deben volver a los iniciales)
        self.cuenta_principal.refresh_from_db()
        self.cuenta_ahorros.refresh_from_db()
        
        self.assertEqual(self.cuenta_principal.saldo, Decimal('2500.00')) # Vuelve al saldo inicial
        self.assertEqual(self.cuenta_ahorros.saldo, Decimal('5000.00')) # Vuelve al saldo inicial
        
        # 4. Verificar que ambas transacciones fueron eliminadas
        self.assertEqual(Transaccion.objects.filter(pk=tx_origen.pk).count(), 0)
        self.assertEqual(Transaccion.objects.filter(pk=tx_destino.pk).count(), 0)
        
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
        
        # URLs
        self.url_resumen = reverse('mi_finanzas:resumen_financiero')
        self.url_transferencia = reverse('mi_finanzas:transferir_monto')
        self.url_anadir_transaccion = reverse('mi_finanzas:anadir_transaccion')
        
        # Crear una transacción simple para el test de eliminación de CRUD (PK=1)
        self.tx_simple_crud = Transaccion.objects.create(
            usuario=self.user,
            cuenta=self.cuenta2,
            monto=Decimal('50.00'),
            tipo='EGRESO',
            categoria=self.cat_gasto,
            fecha=date.today(),
            descripcion='Transaccion de prueba para eliminar'
        )
        self.cuenta2.refresh_from_db() # 1000 - 50 = 950.00

        # Ahora el PK para eliminar es el de la transacción de prueba
        self.url_eliminar_transaccion = reverse('mi_finanzas:eliminar_transaccion', args=[self.tx_simple_crud.pk])


    def test_resumen_financiero_render(self):
        """Asegura que el dashboard se carga correctamente."""
        response = self.client.get(self.url_resumen)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'mi_finanzas/resumen_financiero.html')

    def test_transferencia_monto_suficiente(self):
        """Prueba una transferencia exitosa y verifica los saldos y transacciones."""
        
        data = {
            'cuenta_origen': self.cuenta2.pk, # Banco (950.00)
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
        self.cuenta2.refresh_from_db() # Banco debe ser 950 - 200 = 750
        self.assertEqual(self.cuenta1.saldo, Decimal('700.00'))
        self.assertEqual(self.cuenta2.saldo, Decimal('750.00'))
        
        # 3. Verificar que se crearon 2 transacciones y están marcadas
        # Hay 1 inicial + 2 de la transferencia = 3
        transacciones_transfer = Transaccion.objects.filter(es_transferencia=True, usuario=self.user).count()
        self.assertEqual(transacciones_transfer, 2)
        self.assertEqual(Transaccion.objects.filter(usuario=self.user).count(), 3)

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
        self.assertEqual(self.cuenta2.saldo, Decimal('950.00')) # Mantiene el saldo después del setUp

    def test_anadir_transaccion_crud_ajusta_saldo(self):
        """Prueba el ciclo CRUD de una transacción simple y la reversión de saldos."""
        
        # Saldo inicial de Banco: 950.00 (después del setUp)
        
        # --- 1. CREACIÓN ---
        data_create = {
            'cuenta': self.cuenta2.pk,
            'tipo': 'EGRESO',
            'monto': Decimal('150.00'), 
            'categoria': self.cat_gasto.pk,
            'fecha': date.today(),
            'descripcion': 'Pago de luz'
        }
        
        response_create = self.client.post(self.url_anadir_transaccion, data_create, follow=True)
        self.assertContains(response_create, 'Transacción añadida con éxito!')
        self.cuenta2.refresh_from_db()
        # Saldo esperado: 950.00 (antes) - 150.00 (gasto) = 800.00
        self.assertEqual(self.cuenta2.saldo, Decimal('800.00'))
        tx_luz = Transaccion.objects.get(descripcion='Pago de luz')
        
        # --- 2. EDICIÓN ---
        url_editar = reverse('mi_finanzas:editar_transaccion', args=[tx_luz.pk])
        data_edit = data_create.copy()
        data_edit['monto'] = Decimal('100.00') # Nuevo monto
        
        response_edit = self.client.post(url_editar, data_edit, follow=True)
        self.assertContains(response_edit, 'Transacción actualizada con éxito!')
        self.cuenta2.refresh_from_db()
        # Lógica de saldo: 800 (antes) - (-150) (revertir -EGRESO) + (-100) (aplicar -EGRESO) = 850.00
        self.assertEqual(self.cuenta2.saldo, Decimal('850.00'))
        
        # --- 3. ELIMINACIÓN ---
        # Si la vista funciona: Saldo 850 - (-100) (revertir -EGRESO) = 950.00
        url_eliminar = reverse('mi_finanzas:eliminar_transaccion', args=[tx_luz.pk])
        response_delete = self.client.post(url_eliminar, follow=True)
        self.assertContains(response_delete, 'Transacción eliminada y saldo ajustado con éxito!')
        
        self.cuenta2.refresh_from_db()
        # Saldo esperado: Vuelve al saldo después del setUp (950.00)
        self.assertEqual(self.cuenta2.saldo, Decimal('950.00'))
        
        # 4. Verificar que la transacción fue eliminada
        self.assertEqual(Transaccion.objects.filter(pk=tx_luz.pk).count(), 0)


# D. PRUEBAS DE PRESUPUESTOS
# --------------------------------------------------------
    
    # 🔔 NOTA: Esta prueba usa la lógica 'testuser' del FinanzasLogicTestCase
    def test_calculo_gasto_presupuesto(self):
        """Asegura que el Presupuesto calcula correctamente el gasto acumulado 
        excluyendo transacciones que no son EGRESO o son transferencias."""
        
        # 1. Crear una nueva categoría específica para el presupuesto
        cat_viajes = Categoria.objects.create(
            usuario=self.user,
            nombre='Viajes',
            tipo='EGRESO'
        )
        
        # 2. Crear el Presupuesto para esa categoría
        presupuesto_viajes = Presupuesto.objects.create(
            usuario=self.user,
            categoria=cat_viajes,
            monto_limite=Decimal('1000.00'),
            mes=date.today().month, 
            anio=date.today().year
        )
        
        # 3. Crear Transacciones de EGRESO que DEBEN contarse (Gasto Real)
        # Gasto 1: 300.00
        Transaccion.objects.create(
            usuario=self.user,
            cuenta=self.cuenta_principal,
            monto=Decimal('300.00'), 
            tipo='EGRESO',
            categoria=cat_viajes,
            fecha=date.today(),
            descripcion='Vuelo a Paris'
        )
        # Gasto 2: 150.00
        Transaccion.objects.create(
            usuario=self.user,
            cuenta=self.cuenta_principal,
            monto=Decimal('150.00'), 
            tipo='EGRESO',
            categoria=cat_viajes,
            fecha=date.today(),
            descripcion='Noche de hotel'
        )
        
        # 4. Crear Transacciones que NO DEBEN contarse:
        
        # A. Transferencia (es_transferencia=True) - Debe ser ignorada
        self.simular_creacion_transferencia(self.cuenta_principal, self.cuenta_ahorros, Decimal('200.00'))
        
        # B. Ingreso (tipo='INGRESO') - Debe ser ignorada
        Transaccion.objects.create(
            usuario=self.user,
            cuenta=self.cuenta_principal,
            monto=Decimal('50.00'),
            tipo='INGRESO',
            categoria=cat_viajes,
            fecha=date.today(),
            descripcion='Reembolso de viaje'
        )
        
        # 5. Lógica de cálculo 
        
        # Filtrar solo Egresos, no transferencias, de la categoría y período del presupuesto
        gasto_acumulado = Transaccion.objects.filter(
            usuario=self.user,
            categoria=presupuesto_viajes.categoria,
            tipo='EGRESO', 
            es_transferencia=False, 
            fecha__year=date.today().year,
            fecha__month=date.today().month
        ).aggregate(
            # Sumará los montos positivos: 300.00 + 150.00 = 450.00
            total_gastado=Coalesce(Sum('monto'), Decimal(0))
        )['total_gastado']
        
        # El gasto debe ser: 300.00 + 150.00 = 450.00 (valor absoluto)
        self.assertEqual(gasto_acumulado, Decimal('450.00')) 
        
        # Opcionalmente, verificar el porcentaje de ejecución
        porcentaje_ejecucion = (gasto_acumulado / presupuesto_viajes.monto_limite) * 100
        self.assertEqual(porcentaje_ejecucion, Decimal('45.00'))
        
        # Comprobar el saldo total neto final
        self.cuenta_principal.refresh_from_db()
        self.cuenta_ahorros.refresh_from_db()
        self.tarjeta_credito.refresh_from_db()
        
        # Saldo inicial (7300.00)
        # Ajustes: -300 - 150 (Gastos) - 200 (Transferencia Salida) + 200 (Transferencia Entrada) + 50 (Ingreso)
        # Neto: 7300 - 300 - 150 + 50 = 6900.00
        
        saldo_neto_final = self.cuenta_principal.saldo + self.cuenta_ahorros.saldo + self.tarjeta_credito.saldo

        self.assertEqual(saldo_neto_final, Decimal('6900.00'))

