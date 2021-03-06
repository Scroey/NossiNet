import random
import time
import math

from NossiPack.User import Userlist, User
from NossiSite import app
from NossiSite.helpers import g, session, generate_token, request, redirect, url_for, \
    render_template, flash, connect_db, generate_password_hash, init_db, abort
from NossiPack.Character import Character
from NossiPack.krypta import gendicedata, sumdict

token = {}

init_db()


@app.route('/kudosloan/<user>', methods=['POST'])
def loankudos(user):
    if checktoken():
        if not session.get('logged_in'):
            flash('You are not logged in!')
            return redirect(url_for('login'))
        ul = Userlist()
        loaner = ul.loaduserbyname(session.get('user'))
        loanee = ul.loaduserbyname(user)
        loanee.add_kudosoffer(loaner.username)
        ul.saveuserlist()
        flash("Extended offer for vouching")
    return redirect(url_for('kudosloan'))


@app.route('/setfromdalines/')
def setfromdalines():
    if not session.get('logged_in'):
        flash('You are not logged in!')
        return redirect(url_for('login'))
    number = request.args.get('dalinesnumber')[-7:]
    ul = Userlist()
    u = ul.loaduserbyname(session.get('user'))
    new = Character()
    if new.setfromdalines(number):
        u.sheet = new
        ul.saveuserlist()
        flash("character has been overwritten with provided Dalines sheet!")
    else:
        flash("Problem with Sheetnumber!")
    return redirect(url_for('charsheet'))


@app.route('/dice/<a>,<b>')
def dice(a, b):
    db = connect_db()
    if a == b == 1 == "0": #currently disabled
        print("generating")
        sizes = []
        for i in range(1, 16):
            sizes.append([])
            for j in range(1, 11):
                gendicedata(i, j, 2)
                try:
                    sizes[-1].append(
                        sum([int(x) for x in
                             db.execute("SELECT data "
                                        "FROM dice "
                                        "WHERE amount = ? AND difficulty = ? ",
                                        (i, j)
                                        ).fetchall()[0][0].split(" ") if x]))
                except Exception as inst:
                    sizes[-1].append(0)
        sizes = [[s for s in sublist if s] for sublist in sizes]
        for e in sizes:
            print(e)
        minval, mindex = min((val, idx) for (idx, val) in enumerate([x for x in sizes if x != 0]))
        print(mindex, minval)
        return "done."
    else:
        #   gendicedata(int(a), int(b), 2)
        rows = db.execute("SELECT data "
                          "FROM dice "
                          "WHERE amount = ? AND difficulty = ? ",
                          (a, b)
                          ).fetchall()
        results = {}
        x = 0
        for e in [a for a in rows[0][0].split(" ") if a!='']:
            results[int((-1) ** x * math.ceil(x / 2))] = e
            x += 1
        maximum = max(results.keys())
        total = sumdict(results)
        for e in results.keys():
            results[e] = 100 * int(results[e]) / total  # percent
        result = ""
        for i in range(-maximum, maximum + 1):
                result += str(i) + " = " + str(results.get(i, "<b>0</b>")) + "%<br>"
        return result


@app.route('/kudosloan/', methods=['GET', 'POST'])
def kudosloan():
    if not session.get('logged_in'):
        flash('You are not logged in!')
        return redirect(url_for('login'))
    ul = Userlist()
    u = ul.loaduserbyname(session.get('user'))
    entries = u.get_kudosdebts()
    if request.method == 'POST':
        if checktoken():
            token[session['user']].pop()
            id = request.form['id']
            entry = None
            for e in entries:
                if e.get('id') == id:
                    entry = e
            if entry is not None:
                if entry.get('state') == 'unaccepted':
                    entry['state'] = 'accepted'
                    n = ul.loaduserbyname(entry.get('loaner'))
                    amount = int(n.kudos * 0.1)
                    n.kudos += -amount * 2
                    u.kudos += amount
                    entry['original'] = str(amount)
                    entry['remaining'] = str(amount * 4)
    u.set_kudosdebts(entries)
    ul.saveuserlist()
    for e in entries:
        e['currentkudos'] = ul.loaduserbyname(e.get('loaner')).kudos

    gentoken()
    return render_template('loankudos.html', entries=entries)


@app.route('/')
def show_entries():
    cur = g.db.execute('SELECT author, title, text, plusOned, id FROM entries ORDER BY id DESC')
    entries = [dict(author=row[0], title=row[1], text=row[2], plusoned=row[3], id=row[4]) for row in cur.fetchall()]
    for e in entries:
        if e.get('plusoned') is not None:
            esplit = e.get('plusoned').split(' ')
            e['plusoned'] = ((session.get('user') in esplit) or (session.get('user') == e.get('author')))
        else:
            e['plusoned'] = (session.get('user') == e.get('author'))
        e['text'] = e['text'].replace("\n","<br>")
    gentoken()

    return render_template('show_entries.html', entries=entries)


@app.route('/charactersheet/')
def charsheet():
    if not session.get('logged_in'):
        flash('You are not logged in!')
        return redirect(url_for('login'))
    ul = Userlist()
    u = ul.loaduserbyname(session.get('user'))
    return render_template('charsheet.html', character=u.sheet.getdictrepr(), own=True)


@app.route('/showsheet/<name>')
def showsheet(name="None"):
    if not session.get('logged_in'):
        flash('You are not logged in!')
        return redirect(url_for('login'))
    if name == "None":
        return "error"
    ul = Userlist()
    u = ul.loaduserbyname(name)

    if u:
        if u.sheetpublic or session.get('admin', False):
            return render_template('charsheet.html', character=u.sheet.getdictrepr(), own=False)
        else:
            return render_template('charsheet.html', character=Character().getdictrepr(), own=False)
    else:
        abort(404)


@app.route('/deletesheet/', methods=["POST"])
def del_sheet():
    if not session.get('logged_in'):
        flash('You are not logged in!')
        return redirect(url_for('login'))
    x = int(request.form["sheetnum"])
    ul = Userlist()
    u = ul.loaduserbyname(session.get('user'))
    u.oldsheets.pop(x)
    ul.saveuserlist()
    flash("Sheet deleted from history!")
    return redirect(url_for('oldsheets'))


@app.route('/restoresheet/', methods=["POST"])
def res_sheet():
    if not session.get('logged_in'):
        flash('You are not logged in!')
        return redirect(url_for('login'))
    x = int(request.form["sheetnum"])
    ul = Userlist()
    u = ul.loaduserbyname(session.get('user'))
    newactive = u.oldsheets.pop(x)
    u.oldsheets.append(u.sheet)
    u.sheet = newactive
    ul.saveuserlist()
    flash("Sheet deleted from history!")
    return redirect(url_for('oldsheets'))


@app.route('/map')
def berlinmap():
    return render_template('map.html')


@app.route('/oldsheets/')
def oldsheets():
    if not session.get('logged_in'):
        flash('You are not logged in!')
        return redirect(url_for('login'))
    ul = Userlist()
    u = ul.loaduserbyname(session.get('user'))
    oldsheets = []
    xpdiffs = []
    for i in range(len(u.oldsheets)):
        oldsheets.append(u.oldsheets[i].timestamp)
        if i > 0:
            xpdiffs.append(u.oldsheets[i].get_diff(u.oldsheets[i - 1]))
        else:
            xpdiffs.append(u.oldsheets[i].get_diff(None))
    return render_template('oldsheets.html', oldsheets=oldsheets, xpdiffs=xpdiffs)


@app.route('/showoldsheets/<x>')
def showoldsheets(x):
    if not session.get('logged_in'):
        flash('You are not logged in!')
        return redirect(url_for('login'))
    ul = Userlist()
    u = ul.loaduserbyname(session.get('user'))
    try:
        sheetnum = int(x)
    except:
        return redirect(url_for('/oldsheets/'))
    return render_template('charsheet.html', character=u.oldsheets[sheetnum].getdictrepr(), oldsheet=x)


@app.route('/modify_sheet/', methods=['GET', 'POST'])
def modify_sheet():
    if not session.get('logged_in'):
        flash('You are not logged in!')
        return redirect(url_for('login'))
    ul = Userlist()
    u = ul.loaduserbyname(session.get('user'))
    if request.method == 'POST':
        u.update_sheet(request.form)
        ul.saveuserlist()
        return redirect('/charactersheet/')
    ul.saveuserlist()
    a = render_template('charsheet_editor.html', character=u.sheet.getdictrepr(), Clans=u.sheet.get_clans(),
                        Backgrounds=u.sheet.get_backgrounds())
    return a  # Response(stream_string(a))


@app.route('/timestep/', methods=['GET', 'POST'])
def timestep():
    if not session.get('logged_in'):
        flash('You are not logged in!')
        return redirect(url_for('login'))
    ul = Userlist(preload=True)
    error = None
    keyprovided = session.get('amount') is not None
    if not keyprovided:
        keyprovided = None
    if request.method == 'POST':
        if checktoken():
            try:
                amount = int(request.form['amount'])
                if amount > 0:
                    key = int(time.time())
                    key = generate_password_hash(str(key))
                    print(timestep)
                    print(amount)
                    print(key)
                    session['timekey'] = key[-10:]
                    session['timeamount'] = amount
                    keyprovided = True
                else:
                    error = 'need positive amount'
            except Exception as inst:
                try:
                    key = request.form['key'][-10:]
                    if key == session.pop('timekey'):
                        flash('Passing ' + str(session.get('timeamount')) + ' Days!')
                        for d in range(int(session.pop('timeamount'))):
                            for u in ul.userlist:
                                u.kudos += -int((u.kudos + 70) ** 1.1 * 0.0035)
                                # ^30 ~= 0.9 => 10% tax per month scaling up more harshly, stabilizing at 100

                    else:
                        error = 'wrong key, TimeMagic fizzled...'
                        session.pop('timeamount')
                        session.pop('timekey')
                except Exception as ins:
                    error = 'invalid transaction'
    ul.saveuserlist()
    gentoken()
    return render_template('timestep.html', user=ul.loaduserbyname(session.get('user')),
                           error=error, keyprovided=keyprovided)


@app.route('/plusone/<ident>', methods=['POST'])
def plusone(ident):
    if checktoken():
        entry = {}
        cur = g.db.execute('SELECT author, title, text, plusOned, id FROM entries WHERE id = ?', [ident])
        for row in cur.fetchall():  # SHOULD only run once
            entry = dict(author=row[0], title=row[1], text=row[2], plusoned=row[3], id=row[4])
        ul = Userlist()
        u = ul.loaduserbyname(entry.get('author'))
        if u is None:
            flash("that user is nonexistent, sorry")
            return redirect(url_for('show_entries'))
        if entry.get('author') == session.get('user'):
            flash('upvoting your own posts?')
            return redirect(url_for('show_entries'))

        if entry.get('plusoned') is not None:
            if session.get('user') not in entry.get('plusoned').split(' '):
                entry['plusoned'] = entry.get('plusoned') + ' ' + session.get('user')
                u.kudos += 1
                flash('Gave ' + entry.get('author') + ' Kudos for this post.')
            else:
                flash('already done that')
                return redirect(url_for('show_entries'))
        else:
            entry['plusoned'] = session.get('user')
            u.kudos += 1
            flash('You were the first to give ' + entry.get('author') + ' Kudos for this post.')
        ul.saveuserlist()
        g.db.execute('UPDATE entries SET plusOned = ? WHERE ID = ?', [entry.get('plusoned'), ident])
        g.db.commit()
        gentoken()
    return redirect(url_for('show_entries'))


@app.route('/add', methods=['POST'])
def add_entry():
    if not session.get('logged_in'):
        flash('You are not logged in!')
        return redirect(url_for('login'))
    print(session.get('user', '?'), "adding", request.form)
    if checktoken():
        g.db.execute('INSERT INTO entries (author, title, text) VALUES (?, ?, ?)',
                     [session.get('user'), request.form['title'], request.form['text']])
        g.db.commit()
        flash('New entry was successfully posted')
    gentoken()
    return redirect(url_for('show_entries'))


@app.route('/buy_funds/', methods=['GET', 'POST'])
def add_funds():
    ul = Userlist()
    u = ul.loaduserbyname(session.get('user'))
    error = None
    keyprovided = session.get('amount') is not None
    if not keyprovided:
        keyprovided = None
    if request.method == 'POST':
        if checktoken():
            try:
                amount = int(request.form['amount'])
                if amount > 0:
                    key = int(time.time())
                    key = generate_password_hash(str(key))
                    print("REQUEST BY", u.username, end=" FOR")
                    print(amount, "CREDITS.")
                    print("KEY: ", key)
                    session['key'] = key[-10:]
                    session['amount'] = amount
                    keyprovided = True
                else:
                    error = 'need positive amount'
            except Exception as inst:
                try:
                    key = request.form['key'][-10:]
                    if key == session.pop('key'):
                        flash('Transfer of ' + str(session.get('amount')) + ' Credits was successfull!')
                        u.funds += int(session.pop('amount'))
                    else:
                        error = 'wrong key, transaction invalidated.'
                        session.pop('amount')
                        session.pop('key')
                except Exception as ins:
                    error = 'invalid transaction'

    ul.saveuserlist()
    gentoken()
    return render_template('funds.html', user=u, error=error, keyprovided=keyprovided)


@app.route('/blog/<x>')
def filerender(x):
    try:
        with open("thoughts.txt") as file:
            text = file.read()
        try:
            x = int(x) - 1
            if x < 0:
                x = 0
        except:
            x = 0

        entries = text.split("ÄÄ")

        entries = [i for i in entries if i != ""]
        if x >= len(entries):
            x = len(entries) - 1
        entries.reverse()
        entry = entries[x]
        text = entry
        title = entry.split("\n")[0]

        return render_template('renderfile.html', title=title, torender=text)
    except Exception as j:
        return str(j)


@app.route('/register', methods=['GET', 'POST'])
def register():  # this is not clrs secure because it does not need to be
    error = None
    u = Userlist(None)
    if request.method == 'POST':
        username = request.form['username'].strip()
        if len(username) > 2:
            username = username.upper()
            if request.form['password'] == request.form['passwordcheck']:
                password = request.form['password']
                if len(password) > 0:
                    print("creating user", username)
                    error = u.adduser(username, password)
                    if error is None:
                        flash('User successfully created.')
                        return redirect(url_for('start'))
                else:
                    error = 'Password has to be not empty!'
            else:
                error = 'Passwords do not match!'
        else:
            error = 'Username is too short!'
    return render_template('register.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():  # this is not clrs secure because it does not need to be
    error = None
    ul = Userlist(preload=True, sheets=False)
    if request.method == 'POST':
        user = request.form['username']
        user = user.upper()
        if not ul.valid(user, request.form['password']):
            error = 'invalid username/password combination'
        else:
            session['logged_in'] = True
            session['user'] = user
            session['admin'] = (ul.loaduserbyname(session.get('user')).admin == "Administrator")
            flash('You were logged in')
            print("logged in as", user)

            return redirect(url_for('show_entries'))
    gentoken()
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    flash('You were logged out')
    return redirect(url_for('show_entries'))


@app.route('/nn')
def start():
    return render_template('show_entries.html',
                           entries=[
                               dict(author='the NOSFERATU NETWORK', title='WeLcOmE tO tHe NoSfErAtU nEtWoRk', text='')],
                           heads=['<META HTTP-EQUIV="refresh" CONTENT="5;url=/">'])


@app.route('/regendb/')
def resetdb():
    init_db()
    return "ok "


@app.route('/user/<username>')
def show_user_profile(username):
    msgs = []
    if username == session.get('user'):  # get messages for this user if looking at own page
        cur = g.db.execute(
            'SELECT author,recipient,title,text,value,lock,honored, id FROM messages '
            'WHERE ? IN (recipient, author) ' + ' ORDER BY id DESC',
            (session.get('user'),))
        for row in cur.fetchall():
            msg = dict(author=row[0], recipient=row[1], title=row[2], text=row[3], value=row[4],
                       lock=row[5], honored=row[6], id=row[7])
            cur2 = g.db.execute('SELECT kudosrep, kudosaut FROM messages WHERE id = ?', [msg['id']])
            for row2 in cur2.fetchall():
                msg['kudosrep'] = row2[0]
                msg['kudosaut'] = row2[1]
            if msg['lock']:
                if msg['author'] == username:
                    msg['text'] = '[not yet paid for by ' + msg['recipient'] + ']<br><br>' + msg['text']
                    msg.pop('lock')
                    msg['honored'] = "irrelevant"
                else:
                    msg['text'] = '[locked until you pay]'
            msgs.append(msg)
            #  else:

    ul = Userlist(preload=True)
    if ul.contains(username):
        u = ul.getuserbyname(username)
    else:
        u = User(username, "")
        u.kudos = random.randint(0, 100000)
    ownkudos = 0
    if session.get('logged_in', False):
        ownkudos = ul.getuserbyname(session.get('user')).kudos
    gentoken()
    site = render_template('userinfo.html', ownkudos=ownkudos, user=u, msgs=msgs)
    return site


@app.route('/impressum/')
def impressum():
    return render_template('Impressum.html')


@app.context_processor
def gettoken():
    return dict(token=token.get(session.get('user', None), ''))


def gentoken():
    if session.get('user', False):
        token[session['user']] = generate_token(session)
        return token[session['user']]
    else:
        return ''


def checktoken():
    global token
    if token.get(session.get('user', None), None) != request.form.get('token', "None"):
        # so that None != "None" but a forged token with just "None" inside never matches
        flash("invalid token!")
        print("Token received:" + request.form.get('token', "None") + " Token expected:",
              token.get(session.get('user', None), "INVALID"))
        return False
    else:
        token.pop(session.get('user', ''))
        return True


@app.route('/sendmsg/<username>', methods=['POST'])
def send_msg(username):
    error = None
    if checktoken():
        if not session.get('logged_in'):
            error = 'You are not logged in!'
            return redirect(url_for('login'))
        g.db.execute('INSERT INTO messages (author,recipient,title,text,value,lock,honored)'
                     ' VALUES (?, ?, ?, ?, ?, ?, ?)',  # 7
                     [session.get('user'),  # 1 -author
                      username,  # 2 -recipient
                      request.form['title'],  # 3 title
                      request.form['text'],  # 4 text
                      request.form['price'],  # 5 value
                      not check0(request.form['price']),  # 6 lock
                      check0(request.form['price'])])  # 7 honored
        g.db.commit()
        flash('Message sent')
    return redirect(url_for('show_entries', error=error))


def check0(a):  # used in sendmsg because typecasts in THAT line would make things even worse
    return int(a) == 0


@app.route('/honor/<ident>', methods=['POST', 'GET'])
def honor(ident):
    error = None
    ul = Userlist(preload=True)
    u = ul.loaduserbyname(session.get('user'))
    if checktoken():
        honored = 1
        ul = Userlist()
        author = None
        lock = 0
        u = ul.loaduserbyname(session.get('user'))
        cur = g.db.execute('SELECT author, value, lock, honored FROM messages WHERE id = ?', [ident])
        for row in cur.fetchall():
            author = row[0]
            # value = row[1]
            lock = row[2]
            honored = row[3]
        if author is None:
            error = "The message to be honored seems to be missing"
            return render_template('userinfo.html', user=u, error=error)
        n = ul.loaduserbyname(author)
        if lock != 1:
            if honored != 0:
                error = "This agreement has already been honored."
            else:
                kudosaut = 0
                kudosrep = 0
                cur = g.db.execute('SELECT kudosrep, kudosaut FROM messages WHERE id = ?', [ident])
                for row in cur.fetchall():
                    kudosrep = row[0]
                    kudosaut = row[1]
                u.addkudos(kudosrep)
                n.addkudos(kudosaut)
                g.db.execute('UPDATE messages SET honored = 1 WHERE id = ?', [ident])
                cur = g.db.execute('SELECT * FROM messages')
                flash("Transfer complete. Check the received messsage and "
                      "press the Honor Button if is was what you ordered.")
                g.db.commit()
                ul.saveuserlist()
        else:
            error = 'already unlocked!'
    gentoken()
    return render_template('userinfo.html', user=u, error=error,
                           heads=['<META HTTP-EQUIV="refresh" CONTENT="5;url=' +
                                  url_for('show_user_profile', username=u.username) + '">'])


@app.route('/unlock/<ident>')
def unlock(ident):
    ul = Userlist()
    error = None
    u = None
    lock = 0
    author = ''
    value = 0
    if checktoken():
        u = ul.loaduserbyname(session.get('user'))
        cur = g.db.execute('SELECT author, value, lock FROM messages WHERE id = ?', [ident])
        for row in cur.fetchall():
            author = row[0]
            value = row[1]
            lock = row[2]
        n = ul.loaduserbyname(author)  # n because n = u seen from the other side of the table
        if lock == 1:
            if u.kudos * 0.9 < abs(value):
                error = "You do not have enough kudos for this transaction!"
            elif n.kudos * 0.9 < abs(value):
                error = "Your partner has not enough kudos for this transaction!"
            elif u.funds < value:
                error = "Not enough funds."
            else:
                u.funds -= value
                uescrow = int(
                    0.1 * u.kudos + abs(
                        value))  # (10% of the total Kudos now + twice the value)will be paid upon redemption
                u.addkudos(-uescrow)  # but 10% and the value are deducted now
                uescrow += value
                aftertax = int(value * 0.99)
                tax = value - aftertax  # TAX
                print('taxed')
                print(tax)
                n.funds = int((n.funds + aftertax))
                nescrow = int(0.1 * n.kudos + abs(value))
                n.addkudos(-nescrow)
                nescrow += value
                g.db.execute('UPDATE messages SET lock = 0, kudosrep=?, kudosaut=? WHERE id = ?',
                             [uescrow, nescrow, ident])
                flash("Transfer complete. Check the received message and "
                      "press the Honor Button if it was what you ordered.")
                g.db.commit()
                ul.saveuserlist()
        else:
            flash('already unlocked!')
    gentoken()
    return render_template('userinfo.html', user=u, error=error,
                           heads=['<META HTTP-EQUIV="refresh" CONTENT="5;url=' + url_for('show_user_profile',
                                                                                         username=u.username) + '">'])


@app.route('/ADMINCHEAT/')
def cheat():
    return "DEFUNCT"
    #   ul = Userlist()
    #   u = ul.loaduserbyname("LOCKE")
    #   u.funds = 1000
    #   u.kudos = 4200
    #   ul.saveuserlist()
    #   g.db.execute('UPDATE messages DELETE WHERE id = 8')
    #   g.db.commit()

    #   return 'OK'


@app.route('/resetpassword/', methods=['GET', 'POST'])
def resetpassword():
    if not session.get('logged_in'):
        flash('You are not logged in!')
        return redirect(url_for('login'))
    ul = Userlist()
    u = ul.loaduserbyname(session.get('user'))
    if request.method == 'POST':
        if checktoken():
            try:
                username = request.form['username']
                password = request.form['password']
                newpassword = request.form['newpassword']
                if session.get('admin', False):
                    u = ul.loaduserbyname(username)
                if u.username == username:
                    if u.check_password(password) or session.get('admin', False):
                        u.set_password(newpassword)
                        flash('Password change successfull!')
                    else:
                        flash('Wrong password!')
                else:
                    flash('You are not ' + username)
            except:
                flash('You seem to not exist. Huh...')
                return render_template('resetpassword.html')
    ul.saveuserlist()
    gentoken()
    return render_template('resetpassword.html')


@app.route('/payout/', methods=['GET', 'POST'])
def payout():
    error = None
    if not session.get('logged_in'):
        error = 'You are not logged in!'
        return redirect(url_for('login'))
    ul = Userlist()
    u = ul.loaduserbyname(session.get('user'))
    error = None
    if request.method == 'POST':
        if checktoken():
            try:
                amount = int(request.form['amount'])
                u.funds += -amount
                print('DEDUCT BY', end=" ")
                print(session.get('user'), end=": ")
                print(amount)
                flash('Deduct successfull')
            except:
                error = "Error deducting \"" + request.form.get('amount', 'nothing') + "\"."
    ul.saveuserlist()
    gentoken()
    return render_template('payout.html', user=u, error=error)


@app.route('/deathanddestruction/')
def deldbredir():
    return deldb()


@app.route('/lightswitch/')
def lightswitch(x="None"):
    if session.get('light', False):
        session.pop('light')
    else:
        session["light"] = "ON"
    return redirect(request.referrer)


@app.route('/deathanddestruction/<key>')
def deldb(key="None"):
    db = connect_db()
    if key == "None":
        key = int(time.time())
        key = generate_password_hash(str(key))
        print("KEYOFDEATHINCOMING!")
        print("KEYOFDEATH", key)
        session['deathkey'] = key[-10:]
    else:
        if session.get('deathkey', None) == key[-10:]:
            db.execute('DROP TABLE IF EXISTS entries')
            db.execute('DROP TABLE IF EXISTS messages')
            db.execute('DROP TABLE IF EXISTS users')
            db.commit()
            init_db()
            session.clear()
            return "<link rel=stylesheet type=text/css href=\"/static/style.css\"> " + \
                   "death and destruction has been brought forth"
    return "<link rel=stylesheet type=text/css href=\"/static/style.css\"> DO YOU HAVE THE KEY"


@app.route('/chargen/<mini>,<maxi>,<a>,<b>,<c>')
def chargen(mini, maxi, a, b, c):
    return render_template("chargen.html",
                           char=None)  # makechar(int(mini), int(maxi), int(a), int(b), int(c)).getstringrepr())


@app.route('/favicon.ico')
def favicon():
    return redirect("/static/favicon.ico")
