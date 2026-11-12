import { useEffect, useState } from "react";
import { adminToken, onAdminTokenChange, setAdminToken } from "./admin";

/** Token de administrador da aba, com atualização quando outra tela entra ou sai. */
export function useAdminToken(): [string, (value: string) => void] {
  const [value, setValue] = useState(adminToken());
  useEffect(() => onAdminTokenChange(() => setValue(adminToken())), []);
  return [value, setAdminToken];
}
