import React, { useState } from 'react';
import './Login.css';

const Login = ({ onLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log("Email:", email);
    console.log("Password:", password);
    
    // Backend API na thaka porjonto demo login handle kora
    if (onLogin) {
      onLogin();
    }
  };

  return (
    <div className="login-wrapper">
      <div className="login-box">
        <h2>🌱 AGROVERSE AI</h2>
        <p>Sign in to access your farm dashboard</p>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email Address</label>
            <input 
              type="email" 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email" 
              required 
            />
          </div>

          <div className="form-group">
            <label>Password</label>
            <input 
              type="password" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password" 
              required 
            />
          </div>

          <div className="form-options">
            <label><input type="checkbox" /> Remember me</label>
            <a href="#forgot">Forgot password?</a>
          </div>

          <button type="submit" className="login-btn">Sign In</button>
        </form>
      </div>
    </div>
  );
};

export default Login;