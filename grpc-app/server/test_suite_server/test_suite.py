import unittest

from test_1_login import TestLogin
from test_2_signup import TestSignup
from test_3_send_message import TestSendMessage
from test_4_pending_messages import TestPendingMessages
from test_5_message_delivery_status import TestMessageDeliveryStatus
from test_6_test_invalid_login import TestInvalidLogin
from test_7_auth_required import TestAuthenticationRequired
from test_8_logout_login import TestLogoutLogin
from test_9_send_messsages_to_client import TestSendMessagesToClient
from test_10_delete_single_message import TestDeleteSingleMessage
from test_11_delete_multiple_messages import TestDeleteMultipleMessages
from test_12_delete_account import TestDeleteAccount
from test_13_list_accounts import TestListAccounts

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite([
            unittest.defaultTestLoader.loadTestsFromTestCase(TestLogin),
            unittest.defaultTestLoader.loadTestsFromTestCase(TestSignup),
            unittest.defaultTestLoader.loadTestsFromTestCase(TestSendMessage),
            unittest.defaultTestLoader.loadTestsFromTestCase(TestPendingMessages),
            unittest.defaultTestLoader.loadTestsFromTestCase(TestMessageDeliveryStatus),
            unittest.defaultTestLoader.loadTestsFromTestCase(TestInvalidLogin),
            unittest.defaultTestLoader.loadTestsFromTestCase(TestAuthenticationRequired),
            unittest.defaultTestLoader.loadTestsFromTestCase(TestLogoutLogin),
            unittest.defaultTestLoader.loadTestsFromTestCase(TestSendMessagesToClient),
            unittest.defaultTestLoader.loadTestsFromTestCase(TestDeleteSingleMessage),
            unittest.defaultTestLoader.loadTestsFromTestCase(TestDeleteMultipleMessages),
            unittest.defaultTestLoader.loadTestsFromTestCase(TestDeleteAccount),
            unittest.defaultTestLoader.loadTestsFromTestCase(TestListAccounts)
        ])
    )
