// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: "AIzaSyAIUXLmeksY41WuNLhZ3lvjEMXqlBe35eo",
  authDomain: "gomovo-2a655.firebaseapp.com",
  projectId: "gomovo-2a655",
  storageBucket: "gomovo-2a655.firebasestorage.app",
  messagingSenderId: "196295448533",
  appId: "1:196295448533:web:0e8b719c586089333c0f5c",
  measurementId: "G-LW2T5GTWS5"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);

export { app, analytics };