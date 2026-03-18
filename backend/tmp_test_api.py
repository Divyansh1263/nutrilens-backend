import requests

BASE='http://127.0.0.1:5000'

print('routes', requests.get(BASE+'/routes').status_code)

u='test_user@example.com'
p='testpass'

reg = requests.post(BASE+'/register', json={
    'email': u,
    'password': p,
    'name': 'Test',
    'age': 30,
    'gender': 'M',
    'height': 170,
    'weight': 70,
    'target_weight': 70,
    'activity_level': 'Moderate',
    'dietary_goal': 'Maintain Weight'
})
print('register', reg.status_code, reg.text)

login = requests.post(BASE+'/login', json={'email': u, 'password': p})
print('login', login.status_code, login.text)

if login.status_code == 200:
    data = login.json().get('data')
    user = data.get('user') if isinstance(data, dict) else None
    userId = user.get('userId') if isinstance(user, dict) else None
    print('userId', userId)
    if userId:
        prof = requests.get(BASE + f'/user-profile?userId={userId}')
        print('profile', prof.status_code, prof.text)
        log = requests.post(BASE + '/log-meal', json={
            'userId': userId,
            'date': '2026-03-18',
            'mealName': 'Roti',
            'mealType': 'Lunch',
            'quantity': 1
        })
        print('log', log.status_code, log.text)
        track = requests.get(BASE + f'/tracker-summary?userId={userId}&date=2026-03-18')
        print('tracker', track.status_code, track.text)
        nlp = requests.post(BASE + '/log-meal-nlp-ml', json={
            'userId': userId,
            'date': '2026-03-18',
            'text': '2 roti and dal'
        })
        print('nlp', nlp.status_code, nlp.text)
