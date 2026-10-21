# Bloom Beauty Bar — Product Spec

## Overview
A booking website for a general beauty salon, "Bloom Beauty Bar." Customers
browse the salon's pre-loaded services (hair and nails), book an appointment
by choosing a service and time and giving their contact details, and the
booking is saved. A manage view lists all bookings and allows cancelling one.

## Target users
- **Customers** who want to book a salon appointment online without creating
  an account.
- **Salon staff**, who use the manage view to see and cancel bookings.

## Core concept
Services are a fixed, pre-loaded menu. A booking links a customer (name +
contact) to a service at a chosen date and time. Bookings are the main data
the system creates, lists, and deletes.

## Pre-loaded services
| Service        | Duration | Price |
|----------------|----------|-------|
| Haircut        | 30 min   | R150  |
| Hair Colour    | 90 min   | R450  |
| Root Touch-Up  | 60 min   | R300  |
| Manicure       | 45 min   | R200  |
| Pedicure       | 60 min   | R280  |
| Facial         | 60 min   | R350  |

## Features & user stories

### 1. Browse services
- As a customer, I want to see the list of services with their duration and
  price, so I can choose what to book.
- Acceptance criteria:
  - The services page shows all pre-loaded services with name, duration,
    and price.
  - Services load from the database (seeded at startup), not hardcoded in
    the frontend.

### 2. Book an appointment
- As a customer, I want to book a service at a date and time with my contact
  details, so I can reserve a slot.
- Acceptance criteria:
  - I can select a service, choose a date and time, and enter my name and a
    contact (phone or email).
  - On submit, the booking is saved and confirmed to the customer.
  - A booking that is missing a required field (service, date/time, name, or
    contact) is rejected with a clear message.

### 3. View all bookings
- As salon staff, I want to see all bookings in one place, so I can manage the
  day.
- Acceptance criteria:
  - The manage view lists every booking with its service, date/time, customer
    name, and contact.

### 4. Cancel a booking
- As salon staff, I want to cancel a booking, so the slot is freed and the
  record is removed.
- Acceptance criteria:
  - Cancelling a booking removes it, and it no longer appears in the list.

## Non-goals (deliberately out of scope)
- No customer accounts, logins, or authentication.
- No payments or deposits.
- No admin UI to add/edit/remove services (the menu is fixed/seeded).
- No availability logic or double-booking prevention (any slot can be booked).
- No images, stylist selection, or email/SMS confirmations.
- No rescheduling (cancel and re-book instead).

## Tech (to be decided during build)
- Frontend, backend, and a database, connected end to end.
- Runs locally with a single command (Docker Compose).
- Unit + integration tests.
- Deployed to a public URL, with CI/CD.
- Observability (metrics, logs, traces) on a key journey (booking creation),
  an alert on errors, and an on-call responder agent.
