<script>

function prepareTableDataAndSubmit() {
  const actionType = 'submitted';
  const form = document.getElementById('mainForm');
  const departureDateInput = document.getElementById("departure_date_display1");
  const returnDateInput = document.getElementById("return_date_display1");
  const paymentCheckboxes = document.querySelectorAll(".payment-checkbox");
  const accountNumberField = document.getElementById('accountNumber');

  // Required fields
  const requiredFields = [
      document.querySelector("input[name='name']"),
      document.querySelector("input[name='bu']"),
      document.querySelector("input[name='userEmail']"),
      document.querySelector("input[name='userID']"),
      document.querySelector("input[name='position']"),

      document.querySelector("select[name='dept']"),
      document.querySelector("input[name='departure_date_display']"),
      document.querySelector("input[name='return_date_display']"),
      document.querySelector("input[name='purpose']"),
      document.querySelector("input[name='payment_method']")
  ];

  //Validation for Required Fields
  const missingFields = requiredFields.filter(field => !field || !field.value.trim());
  
    requiredFields.forEach(field => {
      if (field && missingFields.includes(field)) {
          field.classList.add("border-red-500"); // Highlight missing field
          
          // Remove highlight after 5 seconds
          setTimeout(() => {
              field.classList.remove("border-red-500");
          }, 4500);
      }
  });

  //Payment Method Validation
  const isPaymentSelected = [...paymentCheckboxes].some(checkbox => checkbox.checked);
  
  paymentCheckboxes.forEach(checkbox => {
      checkbox.classList.toggle("border-red-500", !isPaymentSelected);
  });

  //Improved Account Number Validation
  const isNonCashSelected = [...paymentCheckboxes].some(checkbox => checkbox.checked && checkbox.value !== "Cash");

  if (isNonCashSelected && !accountNumberField.value.trim()) {
      alert("Please enter account number.");
      accountNumberField.classList.add("border-red-500");
      accountNumberField.focus();
      return;
  } else {
      accountNumberField.classList.remove("border-red-500");
  }

  // Validate Expense Entries
  if (!validateExpenseEntries()) {
    return; // Stop submission if no expense entries
  }


  //Stop Submission if Fields are Missing
  if (missingFields.length > 0 || !isPaymentSelected) {
      alert("Please complete all required fields before saving.");
      return;
  }

  if (!form) {
      console.error('Form not found');
      return;
  }

  //Ensure Departure & Return Dates are Handled Correctly
  if (!departureDateInput.value) {
      departureDateInput.value = "null";
  }
  if (!returnDateInput.value) {
      returnDateInput.value = "null";
  }

  //Proceed with Form Submission
    const formData = new FormData(form);
    formData.append('transportationData', JSON.stringify(dataLists['expenseTableTransport1'] || []));
    formData.append('mealData', JSON.stringify(dataLists['expenseTableMeal1'] || []));
    formData.append('lodgingData', JSON.stringify(dataLists['expenseTableLodging1'] || []));
    formData.append('actionType', actionType);

  
  

  //Debugging Output
  for (let [key, value] of formData.entries()) {
      console.log(`${key}: ${value}`);
  }

  fetch(form.action, {
      method: "POST",
      body: formData,
  })
  .then(response => {
      if (!response.ok) {
          return response.text().then(text => { throw new Error(text || response.status); });
      }
      return response.text();
  })
  .then(data => {
      console.log("Success:", data);
      clearFormFields();  // Clear fields after successful submission
      showSuccessModal(); // Show success modal
  })
  .catch(error => console.error("Error:", error));
}

// Prepare and submit form data with validation
// Tab2
function prepareTableDataAndSubmit1() {
  const actionType = 'submitted';
  const form = document.getElementById('mainFormTab2');
  const departureDateInput = document.getElementById("departure_date_display2");
  const returnDateInput = document.getElementById("return_date_display2");
  const paymentCheckboxes = document.querySelectorAll(".ppayment-checkbox");
  const accountNumberField = document.getElementById('accountNumberTab2');

  // Required fields
  const requiredFields = [
      document.querySelector("input[name='pname']"),
      document.querySelector("input[name='pbu']"),
      document.querySelector("select[name='pdept']"),
      document.querySelector("input[name='ppurpose']")
  ];

    //Validation for Required Fields
    const missingFields = requiredFields.filter(field => !field || !field.value.trim());
    
    requiredFields.forEach(field => {
      if (field && missingFields.includes(field)) {
          field.classList.add("border-red-500"); // Highlight missing field
          
          // Remove highlight after 5 seconds
          setTimeout(() => {
              field.classList.remove("border-red-500");
          }, 4500);
      }
  });

  //Payment Method Validation
  const isPaymentSelected = [...paymentCheckboxes].some(checkbox => checkbox.checked);
  
  paymentCheckboxes.forEach(checkbox => {
      checkbox.classList.toggle("border-red-500", !isPaymentSelected);
  });

  //Improved Account Number Validation
  const isNonCashSelected = [...paymentCheckboxes].some(checkbox => checkbox.checked && checkbox.value !== "Cash");

  if (isNonCashSelected && !accountNumberField.value.trim()) {
      alert("Please enter account number.");
      accountNumberField.classList.add("border-red-500");
      accountNumberField.focus();
      return;
  } else {
      accountNumberField.classList.remove("border-red-500");
  }


  // Validate Expense Entries
  if (!validateExpenseEntries1()) {
    return; // Stop submission if no expense entries
  }


  //Stop Submission if Fields are Missing
  if (missingFields.length > 0 || !isPaymentSelected) {
      alert("Please complete all required fields before saving.");
      return;
  }

  if (!form) {
      console.error('Form not found');
      return;
  }

  //Proceed with Form Submission
    const formData = new FormData(form);
    formData.append('purchaseData', JSON.stringify(dataLists['expenseTablePurchasing_2'] || []));
    formData.append('actionType', actionType);

  //Debugging Output
  for (let [key, value] of formData.entries()) {
      console.log(`${key}: ${value}`);
  }

  fetch(form.action, {
      method: "POST",
      body: formData,
  })
  .then(response => {
      if (!response.ok) {
          return response.text().then(text => { throw new Error(text || response.status); });
      }
      return response.text();
  })
  .then(data => {
      console.log("Success:", data);
      clearFormFields();  // Clear fields after successful submission
      showSuccessModal(); // Show success modal
  })
  .catch(error => console.error("Error:", error));
}
*/


    //Open modal for tab 1 (Cash Advance)
    function openModal(id, table_type) {
        fetch(`/get_main_data/${id}/${table_type}/`)
            .then(response => response.json())
            .then(data => {
                console.log("Fetched data:", data);
                // Populate Main Details
                document.getElementById("caName").textContent = data.main.name;
                document.getElementById("caBusinessUnit").textContent = data.main.businessUnit;
                document.getElementById("caDepartment").textContent = data.main.department;
                document.getElementById("caDateFiled").textContent = formatDate(data.main.dateFiled);
                document.getElementById("caDepartureDate").textContent = formatDate(data.main.departureDate);
                document.getElementById("caReturnDate").textContent = formatDate(data.main.returnDate);
                document.getElementById("caPurpose").textContent = data.main.purpose;
                document.getElementById("payment_mode").textContent = data.main.paymentMode;
                document.getElementById("account_number").textContent = data.main.accountNumber;



                let status = data.main.status;
                let color;
                let table_type = data.main.table_type


                let approveBtn = document.getElementById("approveBtn");
                let rejectBtn = document.getElementById("rejectBtn");



                [approveBtn, rejectBtn].forEach(btn => {
                    if (btn) {
                        btn.style.display = status === 'forapproval' ? "block" : "none";
                        btn.setAttribute("data-id", id);
                        btn.setAttribute("data-table-type", table_type);
                    }
                });


                const statusMap = {
                    draft: "Draft",
                    forapproval: "For Approval",
                    forprocess: "For Process",
                    forrelease: "For Release",
                    pendingliquidation: "Pending Liquidation",
                    denied: "Denied",
                    completed: "Completed"
                };
                
                document.getElementById("caStatus").textContent = statusMap[status] || status;

                document.getElementById("cashAdvanceModal").classList.remove("hidden");
                
                if(table_type === 'CashAdvance'){
                    document.getElementById("table-type").textContent = "ADVANCE";
                    }
                else if(table_type === 'CashReimbursement'){
                    document.getElementById("table-type").textContent = "REIMBURSEMENT";
                }

                // Populate Transportation Table
                let transportTableBody = document.querySelector("#cashAdvanceModal #transportation tbody");
                transportTableBody.innerHTML = ""; // Clear existing rows
                data.transportation.forEach(item => {
                    let row = document.createElement("tr");
                    row.innerHTML = `
                        <td class="p-2 border border-gray-200">${formatDate(item.date)}</td>
                        <td class="p-2 border border-gray-200">${item.locFrom} - ${item.locTo}</td>
                        <td class="p-2 border border-gray-200">${item.amount}</td>
                    `;
                    transportTableBody.appendChild(row);
                });
    
                // Populate Meal Table
                let mealTableBody = document.querySelector("#cashAdvanceModal #meal tbody");
                mealTableBody.innerHTML = "";
                data.meal.forEach(item => {
                    let row = document.createElement("tr");
                    row.innerHTML = `
                        <td class="p-2 border border-gray-200">${formatDate(item.date)}</td>
                        <td class="p-2 border border-gray-200">${item.meal_type}</td>
                        <td class="p-2 border border-gray-200">${item.amount}</td>
                    `;
                    mealTableBody.appendChild(row);
                });
    
                // Populate Lodging Table
                let lodgingTableBody = document.querySelector("#cashAdvanceModal #lodging tbody");
                lodgingTableBody.innerHTML = "";
                data.lodging.forEach(item => {
                    let row = document.createElement("tr");
                    row.innerHTML = `
                        <td class="p-2 border border-gray-200">${formatDate(item.check_in)} - ${formatDate(item.check_out)}</td>
                        <td class="p-2 border border-gray-200">${item.description}</td>
                        <td class="p-2 border border-gray-200">${item.amount}</td>
                    `;
                    lodgingTableBody.appendChild(row);
                });


                // Calculate and Populate Totals
                calculateTotal(data);

                // Populate Rejection Reason (if applicable)
                if (data.main.status === "rejected") {
                    document.getElementById("rejectReasonContainer").classList.remove("hidden");
                    document.getElementById("rejectReasonText").textContent = data.main.rejection_reason;
                } else {
                    document.getElementById("rejectReasonContainer").classList.add("hidden");
                }
                
    
            })
            .catch(error => {
                console.error("Error fetching data:", error);
            });
    }


    // open modal for Tab 2 (Purchase)
    function openModal1(id) {
        fetch(`/get_main_data1/${id}/`)
            .then(response => response.json())
            .then(data => {
                console.log("Fetched data:", data);
                // Populate Main Details
                document.getElementById("pName").textContent = data.main.name;
                document.getElementById("pBusinessUnit").textContent = data.main.businessUnit;
                document.getElementById("pDepartment").textContent = data.main.department;
                document.getElementById("pDate").textContent = formatDate(data.main.dateFiled);
                document.getElementById("pPurpose").textContent = data.main.purpose;
                document.getElementById("ppayment_mode").textContent = data.main.paymentMode;
                document.getElementById("paccount_number").textContent = data.main.accountNumber;

                let status = data.main.status;
                let color;

                const statusMap = {
                    draft: "Draft",
                    forapproval: "For Approval",
                    forprocess: "For Process",
                    forrelease: "For Release",
                    pendingliquidation: "Pending Liquidation",
                    rejected: "Denied",
                    completed: "Completed"
                };
                
                document.getElementById("caStatus").textContent = statusMap[status] || status;

                document.getElementById("purchaseModal").classList.remove("hidden");

                // Populate Purchase Table
                let purchaseTableBody = document.querySelector("#purchaseModal #purchase tbody");
                purchaseTableBody.innerHTML = "";
                data.purchase.forEach(item => {
                    let row = document.createElement("tr");
                    row.innerHTML = `
                        <td class="p-2 border border-gray-200">${formatDate(item.date)}</td>
                        <td class="p-2 border border-gray-200">${item.purchase_number}</td>
                        <td class="p-2 border border-gray-200">${item.particulars}</td>
                        <td class="p-2 border border-gray-200">${item.amount}</td
                    `;
                    purchaseTableBody.appendChild(row);
                });
    
                // Calculate and Populate Totals
                calculateTotal1(data);

                // Populate Rejection Reason (if applicable)
                if (data.main.status === "rejected") {
                    document.getElementById("rejectReasonContainer").classList.remove("hidden");
                    document.getElementById("rejectReasonText").textContent = data.main.rejection_reason;
                } else {
                    document.getElementById("rejectReasonContainer").classList.add("hidden");
                }
    
            })
            .catch(error => {
                console.error("Error fetching data:", error);
            });
    }



</script>