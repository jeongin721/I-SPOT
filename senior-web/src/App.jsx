import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useEffect } from 'react';

// src/pages/<이름>.jsx 를 '/<이름>' 경로로 등록한다(.view.jsx 는 마크업 조각이라 뺀다).
const modules = import.meta.glob(['./pages/*.jsx', '!./pages/*.view.jsx'], { eager: true });
const pages = Object.entries(modules).map(([file, mod]) => ({
  name: file.replace('./pages/', '').replace('.jsx', ''),
  Component: mod.default,
}));

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

export default function App() {
  return (
    <HashRouter>
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<Navigate to="/Login" replace />} />
        {pages.map(({ name, Component }) => (
          <Route key={name} path={`/${name}`} element={<Component />} />
        ))}
        <Route path="*" element={<Navigate to="/Home" replace />} />
      </Routes>
    </HashRouter>
  );
}
