FROM python:3.11-slim

WORKDIR /app

# Ishchi fayllarni nusxalash
COPY . /app

# Kerakli kutubxonalarni o'rnatish
RUN pip install --no-cache-dir aiogram==3.4.1 flask==3.0.2

# Portni ochish
EXPOSE 8080

# Botni ishga tushirish
CMD ["python", "bot.py"]
