/**
 * How a stored timestamp is shown to the reader.
 *
 * Lives here rather than in a view because two components display a job's date:
 * the history row and, once a scan is reopened, the app bar. If each had its
 * own formatter they could disagree about the same timestamp, and the reader
 * would see two dates for one scan with no way to tell which is right.
 *
 * Local time, no timezone suffix: a job seeker reading this is comparing it
 * against when they applied, not against anyone else's clock.
 */
export function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${d.getFullYear()}-${month}-${day} ${hours}:${minutes}`;
  } catch {
    return iso;
  }
}