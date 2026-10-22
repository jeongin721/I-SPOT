import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import Overview from './Overview';
import JobToast from './components/JobToast';

// src/pages/*.jsx 를 모두 읽어 '/파일이름' 경로로 등록해요. (예: /CaseDetail)
const modules = import.meta.glob('./pages/*.jsx', { eager: true });
const pages = Object.entries(modules).map(([file, mod]) => ({
  name: file.replace('./pages/', '').replace('.jsx', ''),
  Component: mod.default,
}));

function ScrollToTop() {
  const { pathname } = useLocation();
  // 중괄호로 감싸 아무것도 돌려주지 않는다. 최신 Chrome 의 scrollTo 는 Promise 를 돌려주는데,
  // 그 값이 effect 정리 함수로 넘어가면 화면을 옮길 때 "destroy is not a function" 으로 앱 전체가 멈춘다.
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
        <Route path="/" element={<Overview />} />
        {pages.map(({ name, Component }) => (
          <Route key={name} path={`/${name}`} element={<Component />} />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {/* 녹취 올리기 · 녹음 저장 뒤 '분석 중 → 분석 완료' 알림(모든 화면 위, 10/22 디자인) */}
      <JobToast />
    </HashRouter>
  );
}
