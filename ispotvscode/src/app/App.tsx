import { RouterProvider } from "react-router";
import { router } from "./routes";
import { ToastProvider } from "../components/ui/Toast";

export default function App() {
  return (
    <ToastProvider>
      <RouterProvider router={router} />
    </ToastProvider>
  );
}
