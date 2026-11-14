import { redirect } from "next/navigation";

export default function FamilyHomePage({ params }: { params: { locale: string } }) {
  redirect(`/${params.locale}/status`);
}
