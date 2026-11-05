// Coleta de arquivos de uma pasta arrastada, preservando o caminho relativo.

export interface PickedFile {
  file: File;
  path: string;
}

const ACCEPTED = /\.(tiff?|jpe?g|png|pdf|zip)$/i;

export function accepted(path: string): boolean {
  const name = path.split("/").pop() ?? "";
  return ACCEPTED.test(path) && !name.startsWith(".");
}

function readEntries(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
  return new Promise((resolve, reject) => reader.readEntries(resolve, reject));
}

async function walk(entry: FileSystemEntry, out: PickedFile[]): Promise<void> {
  if (entry.isFile) {
    const file = await new Promise<File>((resolve, reject) =>
      (entry as FileSystemFileEntry).file(resolve, reject),
    );
    const path = entry.fullPath.replace(/^\//, "");
    if (accepted(path)) out.push({ file, path });
    return;
  }
  const reader = (entry as FileSystemDirectoryEntry).createReader();
  // readEntries devolve em lotes: repete até vir vazio.
  for (;;) {
    const batch = await readEntries(reader);
    if (!batch.length) break;
    for (const child of batch) await walk(child, out);
  }
}

export async function filesFromDrop(items: DataTransferItemList): Promise<PickedFile[]> {
  const entries = Array.from(items)
    .map((i) => i.webkitGetAsEntry())
    .filter((e): e is FileSystemEntry => e !== null);
  const out: PickedFile[] = [];
  for (const entry of entries) await walk(entry, out);
  return out.sort((a, b) => a.path.localeCompare(b.path, "pt-BR", { numeric: true }));
}

export function filesFromInput(list: FileList): PickedFile[] {
  return Array.from(list)
    .map((file) => ({ file, path: file.webkitRelativePath || file.name }))
    .filter((f) => accepted(f.path));
}
