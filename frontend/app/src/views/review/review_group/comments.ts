import * as api from './api';
import { config } from './config';
import { onPageLoaded } from './events';
import { state } from './state';

/** The discussion about the copy (jquery-comments, in the comments modal). */

interface CommentData {
    id: string | number;
    content: string;
    pings: Record<string, string>;
}

/** Saves or updates a comment; pings are written out as names ("@Ada Lovelace"). */
function saveComment(data: CommentData): CommentData {
    for (const [userId, fullName] of Object.entries(data.pings ?? {})) {
        data.content = data.content.replace(new RegExp(`@${userId}`, 'g'), `@${fullName}`);
    }
    if (state.copyNo) api.saveComment(state.copyNo, {comment: JSON.stringify(data)});
    return data;
}

function deleteComment(data: CommentData): CommentData {
    if (state.copyNo) api.saveComment(state.copyNo, {comment_id: data.id, delete: true});
    return data;
}

type Done<T> = (result: T) => void;

function showComments(comments: unknown[]): void {
    $('#comments-container').comments({
        profilePictureURL: 'fa-solid fa-circle-user fa-2xs',
        currentUserId: config.userId,
        roundProfilePictures: true,
        textareaRows: 1,
        enableAttachments: false,
        enableHashtags: false,
        enableUpvoting: false,
        enableEditing: true,
        enableDeleting: true,
        scrollContainer: $(window),
        getComments: (success: Done<unknown[]>) => setTimeout(() => success(comments), 500),
        postComment: (data: CommentData, success: Done<CommentData>) => setTimeout(() => success(saveComment(data)), 500),
        putComment: (data: CommentData, success: Done<CommentData>) => setTimeout(() => success(saveComment(data)), 500),
        deleteComment: (data: CommentData, success: Done<CommentData>) => setTimeout(() => success(deleteComment(data)), 500),
    });
}

export function init(): void {
    onPageLoaded(({data}) => showComments(data.comments));
}
