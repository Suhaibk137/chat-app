// static/script.js

document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    if (room) {
        let mySid = null; // To store the user's own SID

        // Emit join event with the room information
        socket.emit('join', {'room': room});

        // Listen for the 'joined' event to receive the user's SID
        socket.on('joined', (data) => {
            mySid = data.sid;
        });

        // Get references to DOM elements
        const messages = document.getElementById('messages');
        const messageInput = document.getElementById('message-input');
        const imageInput = document.getElementById('image-input');
        const sendButton = document.getElementById('send-button');
        const imagePreview = document.getElementById('image-preview');
        const previewImg = document.getElementById('preview-img');
        const removeImageButton = document.getElementById('remove-image');

        // Event listener for the Send button
        sendButton.addEventListener('click', () => {
            sendMessage();
        });

        // Event listener for pressing Enter in the message input
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // Event listener for image selection
        imageInput.addEventListener('change', () => {
            if (imageInput.files.length > 0) {
                const file = imageInput.files[0];
                const reader = new FileReader();
                reader.onload = function(e) {
                    previewImg.src = e.target.result;
                    imagePreview.style.display = 'flex';
                };
                reader.readAsDataURL(file);
            } else {
                imagePreview.style.display = 'none';
            }
        });

        // Event listener for removing the selected image
        removeImageButton.addEventListener('click', () => {
            imageInput.value = '';
            imagePreview.style.display = 'none';
        });

        // Function to send a message or image
        function sendMessage() {
            const message = messageInput.value.trim();
            const hasImage = imageInput.files.length > 0;

            // Prevent sending empty messages and images
            if (message === '' && !hasImage) {
                return;
            }

            // If there's an image, send it first
            if (hasImage) {
                const file = imageInput.files[0];
                const reader = new FileReader();
                reader.onload = function(e) {
                    const imageData = e.target.result;
                    socket.emit('message', {
                        'room': room,
                        'message': '',
                        'image': imageData
                    });
                };
                reader.readAsDataURL(file);
                imageInput.value = '';
                imagePreview.style.display = 'none';
            }

            // If there's a text message, send it
            if (message !== '') {
                socket.emit('message', {
                    'room': room,
                    'message': message,
                    'image': ''
                });
                messageInput.value = '';
            }
        }

        // Listen for incoming messages
        socket.on('message', (data) => {
            displayMessage(data);
        });

        // Listen for status updates (e.g., user joins)
        socket.on('status', (data) => {
            const statusMsg = document.createElement('div');
            statusMsg.classList.add('status');
            statusMsg.innerText = data.msg;
            messages.appendChild(statusMsg);
            messages.scrollTop = messages.scrollHeight;
        });

        // Listen for error messages
        socket.on('error', (data) => {
            alert(data.msg);
        });

        // Function to display a message in the chat
        function displayMessage(data) {
            const msgDiv = document.createElement('div');
            msgDiv.classList.add('message');

            // Determine if the message is sent or received
            if (data.sender_sid === mySid) {
                msgDiv.classList.add('sent'); // Right-aligned
            } else {
                msgDiv.classList.add('received'); // Left-aligned
            }

            // Add the message text if present
            if (data.message) {
                const msgText = document.createElement('p');
                msgText.innerText = data.message;
                msgDiv.appendChild(msgText);
            }

            // Add the image if present
            if (data.image) {
                const img = document.createElement('img');
                img.src = data.image;
                msgDiv.appendChild(img);
            }

            // Add the timestamp if present
            if (data.timestamp) {
                const timestamp = document.createElement('span');
                timestamp.classList.add('timestamp');
                timestamp.innerText = data.timestamp;
                msgDiv.appendChild(timestamp);
            }

            // Append the message to the messages container
            messages.appendChild(msgDiv);
            messages.scrollTop = messages.scrollHeight; // Auto-scroll to the latest message
        }
    }
});
