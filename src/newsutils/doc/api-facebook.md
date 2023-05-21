


# Getting a Long-lived Facebook Access Token

* https://developers.facebook.com/docs/pages/access-tokens#page-tasks
* Nota:
    Short-lived User access tokens are valid for one hour.
    Long-lived User access tokens are valid for 60 days.
    Short-lived Page access tokens are valid for one hour.
    Long-lived Page access tokens are have no expiration date.


1. Obtain a Short-lived User Access Token (60mn) From the Graph Explorer tool

```bash
SHORT_LIVED_USER_ACCESS_TOKEN=
```

2. Get a Long-lived User Access Token (60d)

```bash
curl -i -X GET "https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=${APP_ID}&client_secret=${APP_SECRET}&fb_exchange_token=${SHORT_LIVED_USER_ACCESS_TOKEN}"
```

{"access_token":"EAAwyeRawKuUBAMupDsQs6FXGyySLCFsL8ZBOPVFDyiQf2aELAQwXTTVY7sZA8mAQd9QE1fRnRvPwMhuOXM3E3nlx8aDUhvBSHvJwCmDpZCVwE0jrz6AmYTvm25ZBn4xrIGHbf7abptXObzOeADyPLeIQ6xfOjj22dmt068mPwAZDZD","token_type":"bearer","expires_in":5143578}


USER_ACCESS_TOKEN=EAAwyeRawKuUBAMupDsQs6FXGyySLCFsL8ZBOPVFDyiQf2aELAQwXTTVY7sZA8mAQd9QE1fRnRvPwMhuOXM3E3nlx8aDUhvBSHvJwCmDpZCVwE0jrz6AmYTvm25ZBn4xrIGHbf7abptXObzOeADyPLeIQ6xfOjj22dmt068mPwAZDZD



3. Get a Long-lived Page Access Token (forever, unless revoked)

```bash
curl -i -X GET "https://graph.facebook.com/$PAGE_ID?fields=access_token&access_token=$USER_ACCESS_TOKEN"
```

{"access_token":"EAAwyeRawKuUBACEMhjDxMbfpd8nShi5WrleHXpbBQSQk6Q859j1cYp2EFoM1enWZCFL7PARGgUmo4fvk88XJIcPCBDOap8OckiCIfhnZC0XQGuxOGQZBNocm8ZAA52J9k2J2TKdJ5bZBmxGUDWZAQ5ow2E7hgPBm92COreO726hJqzY4OaI4Ww","id":"115242378148566"}

