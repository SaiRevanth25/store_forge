import { createBrowserRouter } from "react-router";
import { AuthWrapper } from "./components/AuthWrapper";
import { Login } from "./pages/Login";
import { Signup } from "./pages/Signup";
import { Dashboard } from "./pages/Dashboard";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: AuthWrapper,
    children: [
      { index: true, Component: Dashboard },
      { path: "login", Component: Login },
      { path: "signup", Component: Signup },
    ],
  },
]);