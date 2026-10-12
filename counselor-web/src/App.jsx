import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import Overview from './Overview';

// src/pages/*.jsx 를 모두 읽어 '/파일이름' 경로로 등록해요. (예: /CaseDetail)
const modules = import.meta.glob('./pages/*.jsx', { eager: true });
const pages = Object.entries(modules).map(([file, mod]) => ({
  name: file.replace('./pages/', '').replace('.jsx', ''),
  Component: mod.default,
}));

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => window.scrollTo(0, 0), [pathname]);
  return null;
}

export default function App() {
  return (
    <HashRouter>
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<Overview />} />
        {pages.map(({ name, Component }) => (
          <Route key={name} path={`/${name}`} element={<Component />} />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  );
}
