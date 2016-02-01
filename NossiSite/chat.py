from NossiSite import app, socketio
import time
import threading
from flask import render_template, session, abort, request
from flask_socketio import emit, join_room, leave_room, disconnect
from NossiPack.Chatrooms import Chatroom

thread = None

userlist = {}
rooms = [Chatroom('lobby')]


def statusupdate():
    if session['chatmode'] == 'menu':
        emit('Status', {'status': 'Current Mode: Menu. Type "help" for help.'})
    elif session['activeroom'] not in session['rooms']:
        emit('Status', {'status': 'currently not in any room.'})
    elif session['activeroom'].name not in [x for x in userlist.values()]:
        emit('Status', {'status': 'Currently talking in: "' + session['activeroom'].name + '".'})
    else:
        emit('Status', {'status': 'Currently talking.'})


def echo(message):
    emit('Message', {'data': session['user'] + ": " + message})


def decider(message):
    if message[0] == '/':
        echo(message)
        menucmds(message[1:])
    elif session['chatmode'] == 'menu':
        echo(message)
        menucmds(message)
    elif session['chatmode'] == 'talk':
        if session['activeroom'] is None:
            emit('Message', {'data': 'you are talking to a wall'})
        else:
            print('... in room: ' +session['activeroom'].name)
            session['activeroom'].addline(session['user'] + ": " + message)
            # emit('Message', {'data': session['user'] + ": " + message}, room=session['activeroom'].name)
    statusupdate()


def menucmds(message):
    if message == 'help':
        emit('Message', {'data': '\navailable subscripts:'
                                 '\nwidth  <n>: adjusts page width (35 is standart)'
                                 '\nheight <n>: adjusts height of this box (in pixel)'
                                 '\njoin   <s>: joins room'
                                 '\nleave  <s>: leaves that specific room'
                                 '\nswitch <s>: makes the specified room active'
                                 '\nmenu      : to switch to menu mode'
                                 '\ntalk      : to begin talking'
                                 '\nlog       : to get the log of the room you are in \n'})
    elif message == 'menu':
        session['chatmode'] = 'menu'
    elif message == 'log':
        if session['activeroom'] is not None:
            emit('Message', {'data': '\n#####START###LOG#####\n' + \
                                     session['activeroom'].getlog(session['user'])+ \
                             '######END####LOG#####\n'})
        else:
            emit('Message', {'data': 'no room to get log from!'})
    elif message == 'userlist':
        if session['activeroom'] is not None:
            emit('Message', {'data': '\n#####START###LIST####\n' + \
                                     session['activeroom'].getuserlist_text()+ \
                             '######END####LIST####\n'})
        else:
            emit('Message', {'data': 'no room to get list from!'})
    elif message.split(' ')[0] == 'room':
        emit('Message', {'data': " ".join(x.name for x in session['rooms'] if x != session['rooms'][0])})
    elif message.split(' ')[0] == 'width':
        try:
            width = int(message.split(' ')[1])
        except:
            width = 35
        emit('Message', {'data': '\nadjusting width...\n'})
        emit('Exec', {'command': 'document.getElementById("page_complete").style.width = "' + str(width) + 'em";'})
    elif message.split(' ')[0] == 'height':
        try:
            height = int(message.split(' ')[1])
        except:
            height = 35
        emit('Message', {'data': '\nadjusting height...\n'})
        emit('Exec', {'command': 'document.getElementById("chatbox").style.height = "' + str(height) + 'em";'})

    elif message.split(' ')[0] == 'join':
        try:
            room = message.split(' ')[1]
        except:
            emit('Message', {'data': 'what room?'})
            room = None
        if room is not None:
            emit('Message', {'data': 'subscribing to ' + room + '...'})
            joined = False
            if room in [x.name for x in session['rooms']]:
                emit('Message', {'data': 'already in there!'})
            else:
                joining = rooms[0]
                for r in rooms:
                    if (room == r.name) and (not r.mailbox):
                        r.userjoin(session['user'])
                        session['rooms'].append(r)
                        joined = True
                        joining = r
                if not joined:
                    joining = Chatroom(room)
                    joining.userjoin(session['user'])
                    session['rooms'].append(joining)
                    rooms.append(joining)
                    session['activeroom'] = joining                        
                leave_room(session['activeroom'].name)
                session['activeroom'] = joining
                join_room(session['activeroom'].name)
                emit('Message', {'data': 'done joining!'})

    elif message.split(' ')[0] == 'leave':
        try:
            room = message.split(' ')[1]
        except:
            room = session['activeroom'].name
        emit('Message', {'data': 'unsubscribing from ' + room + '...'})
        left = False
        for r in session['rooms']:
            if (room == r.name) and (not r.mailbox):
                r.userleave(session['user'])
                session['rooms'].remove(r)
                left = True

                emit('Message', {'data': 'removed ' + room})
        if not left:
            emit('Message', {'data': 'not subsrcribed to' + room + '!'})

    elif message.split(' ')[0] == 'switch':
        room = message.split(' ')[1]
        emit('Message', {'data': 'switching to ' + room + '...'})
        switched = False
        for r in session['rooms']:
            if (room == r.name) and (not r.mailbox):
                leave_room(session['activeroom'].name)
                session['activeroom'] = r
                join_room(session['activeroom'].name)
                switched = True
                emit('Message', {'data': 'done switching!'})
            if switched:
                break

        if not switched:
            emit('Message', {'data': 'not subscribed to' + room + '!'})

    elif message == 'talk':
        emit('Message', {'data': '\nentering talk mode, prefix further commands with "/"'
                                 '\neverything else will be sent to the active chat\n\n'})
        session['chatmode'] = 'talk'
        join_room(session['activeroom'].name)

    elif message == 'connection established':
        pass
    else:
        emit('Message', {'data': 'command not found. Type help for help.'})


@app.route('/chat/')
def chatsite():
    if not session.get('logged_in'):
        abort(401)
    global thread
    # if thread is None:
    # thread = threading.Thread(target=background_thread)
    # thread.daemon = True
    # thread.start()
    return render_template('chat.html')


@socketio.on('ClientServerEvent', namespace='/chat')
def test_message(message):
    print(session.get('user', "NoUser"), "\t", message)
    # emit('Message', {'data': session['user'] + ": " + message['data']})
    decider(message['data'])


@socketio.on('Disconnect', namespace='/chat')
def disconnect_request():
    emit('Message',
         {'data': 'Disconnected!'})
    disconnect()


@socketio.on('connect', namespace='/chat')
def chat_connect():
    if not session.get('logged_in'):
        emit('Message', {'prefix': '', 'data': 'Not logged in.'})
        return False
    global userlist
    session['id'] = request.sid
    if session['user']:
        userlist[session['user'].upper()] = session['id']
        mailbox = Chatroom(request.sid)
        mailbox.mailbox = True
        mailbox.users = ''
        rooms.append(mailbox)
        session['rooms'] = [mailbox, rooms[0]]

        try:
            prevmode = session['chatmode']
        except:
            prevmode = 'menu'
        session['chatmode'] = prevmode
        session['activeroom'] = rooms[0]
        rooms[0].userjoin(session['user'])
        join_room(rooms[0])
        emit('Message', {'data': 'Hello and Welcome to the NosferatuNetwork Chatserver.\n'})
    else:
        disconnect()
        return False


@socketio.on('disconnect', namespace='/chat')
def test_disconnect():
    print('Client disconnected', request.sid)
    for r in session['rooms']:
        r.userleave(session['user'])
