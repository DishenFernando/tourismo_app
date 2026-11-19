import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './app/App'
import { AuthenticationProvider } from './app/Auth'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><AuthenticationProvider><App/></AuthenticationProvider></React.StrictMode>
)
