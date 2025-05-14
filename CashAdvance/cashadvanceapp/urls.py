from django.urls import path
from . import views


urlpatterns =[

    path('ca_dashboard', views.ca_dashboard, name='ca_dashboard'),
    path('cr_dashboard', views.cr_dashboard, name='cr_dashboard'),
    path('cl_dashboard', views.cl_dashboard, name='cl_dashboard'),
    
    path("CashAdvance/", views.cashadv, name="cashadvance-page"),
    path("CashReimbursement/", views.cashreim, name="cashreimbursement-page"),
    path("CashLiquidation/", views.cashliq, name="cashliquidation-page"),


    path("Advance/<str:table_type>/", views.saveAdvance, name="save-advance"),
    path("Reimbursement/<str:table_type>/", views.saveReimbursement, name="save-reimbursement"),
    path("Liquidation/<str:table_type>/", views.saveLiquidation, name="save-liquidation"),

    path('get_main_data/<int:main_id>/<str:table_type>/', views.get_main_data, name='get_main_data'),
    path('delete_main_data/<int:main_id>/<str:table_type>/', views.delete_main_data, name='delete-main-data'),

    path('approve-request/<int:main_id>/<str:table_type>/<str:username>/<str:status>/', views.approveRequest, name="approve-request"),
    path('reject-request/<int:main_id>/<str:table_type>/<str:username>/', views.rejectRequest, name="reject-request"),

    path('send-email/', views.send_test_email, name='send_test_email'),

    path('search/<str:db>/', views.search, name='search-item'),

    path('update/<int:id>/<str:table_type>/', views.updateRecord, name='update-page'),



    path('rolsi/', views.rolsi, name='rolsi'),

    
]