// Toggle mobile menu
const menuBtn = document.getElementById('menu-toggle');
const navLinks = document.querySelector('.nav-links');

menuBtn.addEventListener('click', () => {
  navLinks.classList.toggle('active');
});

// Handle login form submission
const loginForm = document.getElementById('login-form');
if (loginForm) {
  loginForm.addEventListener('submit', (e) => {
    e.preventDefault();
    // Simple demo login - in real app, validate credentials
    localStorage.setItem('loggedIn', 'true');
    alert('Login successful!');
    window.location.href = '/menu';
  });
}

// Add animation to "Order Now" buttons
document.querySelectorAll('.order-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    // Check if user is logged in (simple check for demo, in real app use session)
    if (!localStorage.getItem('loggedIn')) {
      alert('Please login first to continue your order.');
      window.location.href = '/login';
      return;
    }
    btn.innerText = "Added!";
    btn.style.background = "#4caf50";
    setTimeout(() => {
      btn.innerText = "Order Now";
      btn.style.background = "#e63946";
    }, 1500);
  });
});



// Show payment details based on method selection
document.addEventListener('DOMContentLoaded', function() {
  const paymentOptions = document.querySelectorAll('input[name="payment_method"]');
  const paymentDetails = document.getElementById('payment-details');

  if (paymentOptions && paymentDetails) {
    paymentOptions.forEach(option => {
      option.addEventListener('change', function() {
        if (this.value === 'GCash' || this.value === 'PayMaya' || this.value === 'COD') {
          paymentDetails.style.display = 'block';
        } else {
          paymentDetails.style.display = 'none';
        }
      });
    });
  }

  // Make payment option cards clickable
  document.querySelectorAll('.payment-option').forEach(option => {
    option.addEventListener('click', function() {
      const radio = this.querySelector('input[type="radio"]');
      radio.checked = true;
      // Trigger change event
      radio.dispatchEvent(new Event('change'));
    });
  });
});

// Toggle sidebar with button
const sidebarToggle = document.getElementById('sidebar-toggle');
const sidebar = document.querySelector('.sidebar');

if (sidebarToggle && sidebar) {
  sidebarToggle.addEventListener('click', function() {
    sidebar.classList.toggle('hidden');
  });
}

// Polling for payment status
function pollPaymentStatus(orderId) {
  const statusDiv = document.getElementById('payment-status');
  const statusText = document.getElementById('status-text');
  statusDiv.style.display = 'block';

  const interval = setInterval(async () => {
    try {
      const response = await fetch(`/payment_status/${orderId}`);
      const data = await response.json();
      statusText.textContent = data.status;
      if (data.status === 'Paid') {
        clearInterval(interval);
        // Redirect to receipt or show success
        setTimeout(() => {
          window.location.href = '/receipt';
        }, 2000);
      }
    } catch (error) {
      console.error('Error polling payment status:', error);
    }
  }, 5000); // Poll every 5 seconds
}

// Check if on payment page and order_id in URL
if (window.location.pathname.startsWith('/payment') && new URLSearchParams(window.location.search).has('order_id')) {
  const orderId = new URLSearchParams(window.location.search).get('order_id');
  pollPaymentStatus(orderId);
}

// Close sidebar when clicking outside
document.addEventListener('click', function(event) {
  const sidebar = document.querySelector('.sidebar');
  const mainContent = document.querySelector('.main-content');
  const sidebarToggle = document.getElementById('sidebar-toggle');

  if (sidebar && mainContent && sidebarToggle && !sidebar.contains(event.target) && !mainContent.contains(event.target) && !sidebarToggle.contains(event.target)) {
    sidebar.classList.add('hidden');
  }
});



// Payment page item management
document.addEventListener('DOMContentLoaded', function() {
  const addItemForm = document.getElementById('add-item');
  const cartItems = document.getElementById('cart-items');
  const cartTotal = document.getElementById('cart-total');

  if (addItemForm) {
    addItemForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const name = document.getElementById('new-item-name').value;
      const price = parseFloat(document.getElementById('new-item-price').value);
      if (name && price) {
        fetch('/add_item_payment', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: `item_name=${encodeURIComponent(name)}&item_price=${price}`
        })
        .then(response => response.json())
        .then(data => {
          updateCartDisplay(data.cart, data.total);
          document.getElementById('new-item-name').value = '';
          document.getElementById('new-item-price').value = '';
        });
      }
    });
  }

  if (cartItems) {
    cartItems.addEventListener('click', function(e) {
      const item = e.target.closest('.cart-item');
      const index = item.dataset.index;

      if (e.target.classList.contains('edit-btn') || e.target.closest('.edit-btn')) {
        // Switch to edit mode
        item.querySelector('.item-display').style.display = 'none';
        item.querySelector('.item-edit').style.display = 'flex';
        item.querySelector('.edit-btn').style.display = 'none';
        item.querySelector('.save-btn').style.display = 'inline-flex';
        // Smooth transition
        item.style.transition = 'all 0.3s ease';
      } else if (e.target.classList.contains('save-btn') || e.target.closest('.save-btn')) {
        const name = item.querySelector('.item-name').value;
        const price = parseFloat(item.querySelector('.item-price').value);
        if (name && price) {
          fetch(`/edit_item_payment/${index}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `item_name=${encodeURIComponent(name)}&item_price=${price}`
          })
          .then(response => response.json())
          .then(data => {
            updateCartDisplay(data.cart, data.total);
          });
        }
      } else if (e.target.classList.contains('remove-btn') || e.target.closest('.remove-btn')) {
        fetch(`/remove_item_payment/${index}`, {
          method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
          updateCartDisplay(data.cart, data.total);
        });
      }
    });
  }

  function updateCartDisplay(cart, total) {
    cartItems.innerHTML = cart.map((item, index) => `
      <div class="cart-item" data-index="${index}">
        <div class="item-display">
          <span class="item-name-display">${item.name}</span>
          <span class="item-price-display">₱${item.price.toFixed(2)}</span>
        </div>
        <div class="item-edit" style="display:none;">
          <input type="text" class="item-name" value="${item.name}">
          <input type="number" class="item-price" value="${item.price}" step="0.01">
        </div>
        <div class="item-actions">
          <button class="edit-btn" title="Edit Item"><i class="edit-icon">✏️</i> Edit</button>
          <button class="save-btn" style="display:none;" title="Save Changes"><i class="save-icon">💾</i> Save</button>
          <button class="remove-btn" title="Remove Item"><i class="remove-icon">🗑️</i></button>
        </div>
      </div>
    `).join('');
    cartTotal.textContent = total.toFixed(2);
  }

// Payment status polling
  let orderId = null;
  const paymentForm = document.querySelector('.payment-form');
  const paymentStatus = document.getElementById('payment-status');
  const statusText = document.getElementById('status-text');

  if (paymentForm) {
    paymentForm.addEventListener('submit', function(e) {
      // Allow form submission, but show status for realtime payments
      const selectedMethod = document.querySelector('input[name="payment_method"]:checked');
      if (selectedMethod && (selectedMethod.value === 'GCash' || selectedMethod.value === 'PayMaya')) {
        paymentStatus.style.display = 'block';
        statusText.textContent = 'Processing...';
        // In production, get orderId from response or session
        // For demo, simulate polling
        setTimeout(() => pollPaymentStatus(), 2000);
      }
    });
  }

  function pollPaymentStatus() {
    if (!orderId) return; // In production, set orderId from form submission response
    fetch(`/payment_status/${orderId}`)
      .then(response => response.json())
      .then(data => {
        statusText.textContent = data.status;
        if (data.status === 'Paid') {
          // Redirect or update UI
          window.location.href = `/receipt?order_id=${orderId}`;
        } else if (data.status === 'Processing') {
          setTimeout(() => pollPaymentStatus(), 5000); // Poll every 5 seconds
        }
      })
      .catch(error => console.error('Error polling status:', error));
  }

  // Function to fetch and update user order history and notifications
  async function fetchUserOrders() {
    try {
      const response = await fetch('/api/user_orders');
      if (response.ok) {
        const data = await response.json();
        updateOrderHistory(data.order_history);
        updateNotifications(data.notifications);
      }
    } catch (error) {
      console.error('Error fetching user orders:', error);
    }
  }

  // Function to update order history
  function updateOrderHistory(orderHistory) {
    const historyList = document.getElementById('order-history-list');
    if (historyList) {
      historyList.innerHTML = '';
      orderHistory.forEach(order => {
        const li = document.createElement('li');
        li.className = 'history-item';
        li.innerHTML = `
          <strong>Date:</strong> ${order.date}<br>
          <strong>Items:</strong> ${order.items.join(', ')}<br>
          <strong>Status:</strong> <span class="status-${order.status.toLowerCase()}">${order.status}</span>
        `;
        historyList.appendChild(li);
      });
    }
  }

  // Function to update notifications
  function updateNotifications(notifications) {
    const notificationsList = document.getElementById('notifications-list');
    if (notificationsList) {
      notificationsList.innerHTML = '';
      notifications.forEach(note => {
        const li = document.createElement('li');
        li.className = 'notification-item';
        li.textContent = note;
        notificationsList.appendChild(li);
      });
    }
  }

  // Fetch user orders on page load and set up polling for dashboard
  if (window.location.pathname === '/dashboard') {
    fetchUserOrders();
    setInterval(fetchUserOrders, 5000); // Update every 5 seconds
  }
});
