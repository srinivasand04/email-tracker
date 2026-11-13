export const metadata = { title: "Privacy · Email Tracker" };

export default function Privacy() {
  return (
    <main className="prose">
      <h1>Privacy</h1>
      <p>
        Email Tracker is a personal tool used only by its owner. It is not offered to anyone else, and
        sign-in is limited to the owner&apos;s own Google accounts.
      </p>
      <h2>What it reads</h2>
      <p>
        With read-only Gmail access (<code>gmail.readonly</code>) granted by the owner, it reads new mail in
        the owner&apos;s accounts. It cannot send, delete or change any email.
      </p>
      <h2>What it stores</h2>
      <p>
        For each email: the account, sender, subject, date, Gmail labels, a short snippet, a category, a
        priority, a one-line summary and a link back to Gmail. The first part of the body is kept only until
        the email is classified, then deleted. Full emails and attachments are never stored. Data is kept in
        the owner&apos;s private database and is not shared with or sold to anyone.
      </p>
      <h2>Classification</h2>
      <p>
        Emails are sorted by rules and by a language model running on the owner&apos;s own computer. Email
        content is not sent to third-party AI services.
      </p>
      <h2>Removing access</h2>
      <p>
        Access can be withdrawn at any time at{" "}
        <a href="https://myaccount.google.com/permissions">myaccount.google.com/permissions</a>.
      </p>
    </main>
  );
}
