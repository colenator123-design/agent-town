on clean_text(value)
    set text_value to value as text
    set AppleScript's text item delimiters to {tab, return, linefeed}
    set pieces to text items of text_value
    set AppleScript's text item delimiters to " "
    set text_value to pieces as text
    set AppleScript's text item delimiters to ""
    return text_value
end clean_text

set start_of_today to current date
set hours of start_of_today to 0
set minutes of start_of_today to 0
set seconds of start_of_today to 0
set output to ""

tell application "Mail"
    set today_messages to messages of inbox whose date received ≥ start_of_today
    set message_count to count of today_messages
    if message_count > 300 then set message_count to 300
    repeat with message_index from 1 to message_count
        set current_message to item message_index of today_messages
        set message_sender to my clean_text(sender of current_message)
        set message_subject to my clean_text(subject of current_message)
        set unread_value to not (read status of current_message)
        set flagged_value to flagged status of current_message
        set output to output & message_sender & tab & message_subject & tab & unread_value & tab & flagged_value & linefeed
    end repeat
end tell

return output
