from pcommerce.core.data import PaymentData

def SpreedlyPaymentData():
    data  = PaymentData('nuw.types.spreedly')
    
    data.card_types = {'visa':'Visa', 'master':'MasterCard', 'american_express':'American Express', 'discover':'Discover', 'dankort':'Dankort'}
    data.paymentstepid = None
    data.processstepid = None

    data.errors = None
    data.person_id = None
    data.connection = None
    data.gateway = None
    data.token = None
    data.method = None
    data.methods_count = 0
    data.transaction = None
    
    # Flags
    data.needprocessform = True
    data.processingtoken = False

    return data
