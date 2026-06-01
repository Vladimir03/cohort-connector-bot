import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import UsersPage from "./pages/Users";
import EventsPage from "./pages/Events";
import BroadcastPage from "./pages/Broadcast";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="events" element={<EventsPage />} />
        <Route path="broadcast" element={<BroadcastPage />} />
      </Route>
    </Routes>
  );
}
