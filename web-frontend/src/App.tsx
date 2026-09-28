import { Routes, Route } from 'react-router-dom';
import Splash from './pages/Splash';
import Dashboard from './pages/Dashboard';
import Cases from './pages/Cases';
import Schedule from './pages/Schedule';
import Records from './pages/Records';
import DataReview from './pages/DataReview';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Splash />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/cases" element={<Cases />} />
      <Route path="/schedule" element={<Schedule />} />
      <Route path="/records" element={<Records />} />
      <Route path="/reviews" element={<DataReview />} />
    </Routes>
  );
}

export default App;
